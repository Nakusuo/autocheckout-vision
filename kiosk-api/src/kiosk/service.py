import itertools
import logging
import time
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass

from kiosk.catalog import Catalog
from kiosk.checkout import MAX_ITEMS, Checkout, State, TransitionError
from kiosk.fusion import Cart, build_cart, check_weight
from kiosk.metrics import SessionRecorder
from kiosk.payments import (
    Charge,
    JwtVerifier,
    PaymentError,
    PaymentGateway,
    UnverifiedPayment,
    YapeProvider,
    YapeResult,
    parse_wallet_notification,
    yape_message,
)
from kiosk.pos import SimulatedPos
from kiosk.scale import ScaleReader
from kiosk.stability import StabilityFilter
from kiosk.tray import Detector

log = logging.getLogger(__name__)

RESET_AFTER_S = 10.0
PAYMENT_TIMEOUT_S = 120.0
POLL_EVERY_S = 1.0
MAX_YAPE_ATTEMPTS = 3  # rechazos seguidos antes de pedir ayuda en caja
# Margen antes de alertar por peso: el cliente pasa el producto y lo deja en la bandeja
# un instante después. PAGAR sigue bloqueado mientras el peso no coincida.
WEIGHT_GRACE_S = 2.0


@dataclass(frozen=True)
class Reading:
    """Lo que vieron los sensores en un instante: SKUs a la vista y gramos (None sin balanza)."""

    skus: list[str]
    grams: float | None


MAX_PENDING = 50  # ayudas y alertas sin atender que se guardan

SCREEN = {
    State.IDLE: "W1",
    State.SCANNING: "W2",
    State.CONFIRMING: "W3",
    State.PAYING: "QR",
    State.PAID: "W4",
    State.OUT_OF_SERVICE: "FUERA_DE_SERVICIO",
}


class KioskService:
    def __init__(
        self,
        catalog: Catalog,
        detector: Detector,
        scale: ScaleReader | None,
        gateway: PaymentGateway,
        verifier: JwtVerifier | None,
        clock: Callable[[], float] = time.monotonic,
        pos: SimulatedPos | None = None,
        sessions: SessionRecorder | None = None,
        on_cart: Callable[[Cart], None] | None = None,
        yape: YapeProvider | None = None,
        wallet_qr: str | None = None,
        browser_camera: bool = False,
    ):
        """Medios de pago (uno a la vez; `gateway` y `verifier` solo se usan con el QR simulado):
        - `yape`: Yape vía Mercado Pago (celular + código de aprobación).
        - `wallet_qr`: URL de la imagen del QR propio de Yape/Plin del comercio; el pago se da por
          hecho con la notificación que llega al celular (`wallet_notification`).
        `browser_camera`: la cámara está en el navegador (o la app) y sugiere productos que el
        cliente agrega con `add_product`."""
        self.catalog = catalog
        self._detector = detector
        self._open_camera = getattr(detector, "open", None)
        self._close_camera = getattr(detector, "close", None)
        self._scale = scale
        self._gateway = gateway
        self._verifier = verifier
        self._clock = clock
        self.pos = pos if pos is not None else SimulatedPos()
        self.sessions = sessions if sessions is not None else SessionRecorder()
        self._weight_alerted = False
        # Escaneo uno por uno: lo escaneado se acumula; un producto se suma cuando entra
        # a la vista de la cámara, no mientras sigue ahí.
        self._scanned: Counter[str] = Counter()
        self._view: Counter[str] = Counter()
        self._last_grams = 0.0
        self._mismatch_since: float | None = None
        self._on_cart = on_cart
        self.checkout = Checkout(require_weight=scale is not None)
        self._stability = StabilityFilter()
        self._entered_at = clock()
        self.help_requests: list[dict] = []
        self._next_help_id = 1
        # Alertas de seguridad para la caja: nadie vigila todo el tiempo; se avisa si pasa algo raro
        self.security_alerts: list[dict] = []
        self._next_alert_id = 1
        self._sale_alert: dict | None = None  # una alerta por compra; se actualiza, no se repite
        self._charge: Charge | None = None
        self._reference = ""
        self._last_poll = float("-inf")
        self._references = itertools.count(1)
        self._yape = yape
        self._yape_busy = False  # hay una llamada a Mercado Pago en curso
        self._yape_error: str | None = None
        self._yape_attempts = 0
        self._wallet_qr = wallet_qr
        self._browser_camera = browser_camera
        self._receipt: dict | None = None  # boleta de la venta recién pagada (pantalla W4)
        self._payer: str | None = None

    def _do(self, action: Callable[[], None]) -> None:
        before = self.checkout.state
        action()
        if self.checkout.state is not before:
            self._entered_at = self._clock()
            if self.checkout.state is State.SCANNING:
                self._stability.reset()
            if self.checkout.state is not State.PAYING:
                self._charge = None
                self._yape_error = None
                self._yape_attempts = 0
            if self.checkout.state is not State.PAID:
                self._receipt = None
                self._payer = None
            if self._close_camera is not None:
                camera_action = self._open_camera if self.wants_reading() else self._close_camera
                if camera_action is not None:
                    camera_action()

    def start(self) -> None:
        self._do(self.checkout.start)
        self.sessions.begin(self._clock(), weight_checked=self._scale is not None)
        self._weight_alerted = False
        self._close_alert("sin cerrar")  # no debería quedar ninguna; si queda, no se pierde
        self._scanned = Counter()
        self._view = Counter()
        self._cart_changed()

    def confirm(self) -> None:
        self._do(self.checkout.confirm)

    def cancel(self) -> None:
        """El cliente abandona la compra: se descarta la lista (y el cobro, si había QR)."""
        if self._yape_busy:
            raise TransitionError("Espere: se está procesando el pago con Yape")
        screen = SCREEN[self.checkout.state]
        self._do(self.checkout.cancel)
        self._scanned = Counter()
        self._view = Counter()
        self._cart_changed()
        self._close_alert("cancelada")
        self.sessions.finish(self._clock(), "cancelled", screen=screen)

    def add_product(self, sku: str) -> None:
        """El cliente agrega el producto que sugirió la cámara del navegador (un toque = 1)."""
        if self.checkout.state is not State.SCANNING:
            raise TransitionError(f"Acción no permitida en el estado {self.checkout.state.value}")
        if self.catalog.get(sku) is None:
            raise TransitionError("Ese producto no está en el catálogo")
        self._scanned[sku] += 1
        self._cart_changed()
        self._refresh(self._last_grams if self._scale is not None else None)

    def remove(self, sku: str) -> None:
        """El cliente quita una unidad de la lista (p. ej., la cámara la contó dos veces)."""
        if self.checkout.state is not State.SCANNING:
            raise TransitionError(f"Acción no permitida en el estado {self.checkout.state.value}")
        if self._scanned[sku] <= 0:
            raise TransitionError("Ese producto no está en la lista")
        self._scanned[sku] -= 1
        self.sessions.note("removals")
        self._cart_changed()
        self._refresh(self._last_grams if self._scale is not None else None)

    def correct(self) -> None:
        self._do(self.checkout.correct)
        self.sessions.note("corrections")

    def pay(self) -> None:
        cart = self.checkout.cart
        if not self.checkout.can_pay or cart is None:
            self._do(self.checkout.pay)  # lanza TransitionError con el motivo
            return
        reference = f"venta-{next(self._references)}"
        if self._yape is not None or self._wallet_qr is not None:
            # Yape con código o QR propio: no hay cobro que crear en una pasarela
            self._do(self.checkout.pay)
            self._reference = reference
            return
        try:
            charge = self._gateway.create_charge(cart.total_cents, reference)
        except PaymentError as e:
            raise TransitionError("No se pudo generar el código QR. Intente de nuevo") from e
        self._do(self.checkout.pay)
        self._charge = charge
        self._reference = reference
        self._last_poll = float("-inf")

    def accept_payment(self) -> None:
        """La caja aprueba el cobro simulado vigente; se valida el token firmado."""
        if self.checkout.state is not State.PAYING or self._charge is None:
            raise TransitionError("No hay un pago pendiente para aprobar")
        try:
            self._gateway.confirm(self._charge.id)
        except PaymentError as e:
            raise TransitionError("No se pudo aprobar el pago. Intente de nuevo") from e
        self._last_poll = float("-inf")
        self._poll_payment()

    def begin_yape(self) -> tuple[int, str]:
        """Reserva el cobro con Yape: valida el estado y devuelve (monto, referencia).

        No hace red. Mientras dure el cobro no se puede cancelar ni vence el tiempo, para no
        cobrar una compra que ya se descartó."""
        cart = self.checkout.cart
        if self._yape is None:
            raise TransitionError("Este quiosco no cobra con Yape")
        if self.checkout.state is not State.PAYING or cart is None:
            raise TransitionError("No hay un cobro en curso")
        if self._yape_busy:
            raise TransitionError("Ya se está procesando el pago")
        if self._yape_attempts >= MAX_YAPE_ATTEMPTS:
            raise TransitionError("Demasiados intentos. Pida ayuda en caja")
        self._yape_busy = True
        self._yape_error = None
        return cart.total_cents, self._reference

    def charge_yape(
        self, amount_cents: int, reference: str, phone: str, otp: str
    ) -> YapeResult | PaymentError:
        """La parte lenta (red): puede correr en otro hilo, no toca el estado."""
        if self._yape is None:
            return PaymentError("Este quiosco no cobra con Yape")
        try:
            return self._yape.charge(amount_cents, reference, phone, otp)
        except PaymentError as e:
            return e
        except Exception as e:  # un fallo inesperado no debe dejar el cobro «en curso» para siempre
            log.exception("Error inesperado al cobrar con Yape")
            return PaymentError(f"Error inesperado: {e}")

    def finish_yape(
        self, reference: str, amount_cents: int, outcome: YapeResult | PaymentError
    ) -> None:
        """Aplica el resultado del cobro (en el bucle principal)."""
        self._yape_busy = False
        if isinstance(outcome, UnverifiedPayment):
            # Quizá ya se cobró: sin reintentos, la caja revisa la operación.
            self._yape_attempts = MAX_YAPE_ATTEMPTS
            self._yape_error = "No se pudo verificar el pago. Pida ayuda en caja"
            self._cashier_alert(
                f"Pago Yape aprobado sin verificar ({reference}, operación "
                f"{outcome.payment_id}, S/ {outcome.amount_cents / 100:.2f}): revisar en Mercado Pago"
            )
            log.error("Pago Yape %s aprobado sin verificar: %s", outcome.payment_id, outcome)
            return
        if isinstance(outcome, PaymentError):
            log.warning("Cobro con Yape fallido: %s", outcome)
            self._yape_error = "No se pudo conectar con Yape. Intente de nuevo"
            return
        if not outcome.approved:
            self._yape_attempts += 1
            log.info("Yape rechazó %s: %s", reference, outcome.status_detail)
            self._yape_error = yape_message(outcome.status_detail)
            if self._yape_attempts >= MAX_YAPE_ATTEMPTS:
                self._yape_error += ". Demasiados intentos: pida ayuda en caja"
            return
        cart = self.checkout.cart
        if (
            cart is None
            or self.checkout.state is not State.PAYING
            or reference != self._reference
            or not cart.total_cents == amount_cents == outcome.amount_cents
        ):
            self._orphan_payment(outcome, reference)
            return
        self._complete_sale(reference, outcome.payment_id, cart)

    def wallet_notification(self, text: str, simulated: bool = False) -> dict:
        """Notificación de pago recibido en el celular del comercio (Yape/Plin a su QR).

        Se acepta solo si hay un cobro esperando y el monto es exactamente el total. Con
        `simulated` (demo, /sim) la boleta queda con `charge_id` «sim-billetera-…». Devuelve
        `{"matched": bool, "reason"?: str, "receipt"?: str}` para quien la envió.
        RIESGO CONOCIDO: un pago ajeno por el mismo monto, durante la espera, se tomaría como este.
        """
        if self._wallet_qr is None:
            raise TransitionError("Este quiosco no cobra con QR de Yape/Plin")
        notice = parse_wallet_notification(text)
        if notice is None:
            return {"matched": False, "reason": "No se encontró un monto en la notificación"}
        cart = self.checkout.cart
        if self.checkout.state is not State.PAYING or cart is None:
            return {"matched": False, "reason": "No hay un cobro esperando pago"}
        if notice.amount_cents != cart.total_cents:
            return {
                "matched": False,
                "reason": f"Monto distinto: llegó S/ {notice.amount_cents / 100:.2f}, "
                f"se espera S/ {cart.total_cents / 100:.2f}",
            }
        charge_id = f"{'sim-' if simulated else ''}billetera-{self._reference}"
        self._complete_sale(self._reference, charge_id, cart)
        self._payer = notice.payer
        receipt = self._receipt or {}
        log.info("Pago por QR recibido para %s (%s)", self._reference, receipt.get("number"))
        return {"matched": True, "receipt": receipt.get("number")}

    def _complete_sale(self, reference: str, charge_id: str, cart: Cart) -> None:
        """Cierra la venta pagada: W4, boleta, alerta de la compra y registro de la sesión."""
        self._do(self.checkout.payment_confirmed)
        self._receipt = self.pos.issue_receipt(reference, charge_id, cart.lines, cart.total_cents)
        self._close_alert("pagada")
        self.sessions.finish(self._clock(), "paid", cart.item_count, cart.total_cents)

    def _orphan_payment(self, outcome: YapeResult, reference: str) -> None:
        """Mercado Pago aprobó un cobro que ya no corresponde a la compra en pantalla: la caja
        debe devolverlo."""
        self._cashier_alert(
            f"Pago Yape aprobado sin compra en curso ({reference}, operación "
            f"{outcome.payment_id}, S/ {outcome.amount_cents / 100:.2f}): devolver"
        )
        log.error("Pago Yape %s aprobado sin compra en curso", outcome.payment_id)

    def _cashier_alert(self, reason: str) -> None:
        """Alerta de dinero para la caja: nunca se descarta sola (outcome «pagada»)."""
        self.security_alerts.append(
            {
                "id": self._next_alert_id,
                "reason": reason,
                "screen": SCREEN[self.checkout.state],
                "at": self._clock(),
                "times": 1,
                "outcome": "pagada",
            }
        )
        self._next_alert_id += 1
        self._trim_alerts()

    def recover(self) -> None:
        self._do(self.checkout.recover)

    def set_scale(self, scale: ScaleReader | None) -> None:
        """Conecta o quita la balanza (simulador y pruebas). Solo en W1: no cambia una compra."""
        if self.checkout.state is not State.IDLE:
            raise TransitionError("La balanza solo se cambia con el quiosco en W1")
        self._scale = scale
        self.checkout = Checkout(require_weight=scale is not None)

    def recalibrate(self) -> None:
        """Vuelve a aprender la bandeja vacía (la cámara se movió o había algo al arrancar)."""
        recalibrate = getattr(self._detector, "recalibrate", None)
        if recalibrate is None:
            raise TransitionError("Este modo no usa cámara")
        recalibrate()

    def wants_reading(self) -> bool:
        """En W1 también se lee: la cámara sigue aprendiendo la bandeja vacía."""
        return self.checkout.state in (State.IDLE, State.SCANNING) or (
            self.checkout.state is State.CONFIRMING and self._close_camera is None
        )

    def read_sensors(self) -> Reading:
        """La parte lenta (cámara + reconocimiento): puede correr en otro hilo, no toca el estado."""
        skus = self._detector.detect() if self.wants_reading() else list(self._view.elements())
        grams = self._scale.read() if self._scale is not None else None
        return Reading(skus, grams)

    def tick(self, reading: Reading | Exception | None = None) -> None:
        """Avanza el quiosco. `reading` viene del hilo de la cámara; sin él, se lee aquí mismo."""
        state = self.checkout.state
        elapsed = self._clock() - self._entered_at
        if state is State.PAID and elapsed >= RESET_AFTER_S:
            self._do(self.checkout.reset)
            return
        if state is State.PAYING and self._yape_busy:
            return  # no vence ni se consulta mientras Mercado Pago responde
        if state is State.PAYING and elapsed >= PAYMENT_TIMEOUT_S:
            self._do(self.checkout.payment_timeout)
            self.sessions.note("payment_timeouts")
            return
        if state is State.PAYING:
            self._poll_payment()
            return
        if state not in (State.SCANNING, State.CONFIRMING):
            return
        if state is State.CONFIRMING and self._close_camera is not None:
            reading = None  # descarta cuadros que terminaron después de apagar la cámara
        if reading is None:
            try:
                reading = self.read_sensors()
            except Exception as e:  # noqa: BLE001 - cualquier fallo de sensor detiene el quiosco
                reading = e
        if isinstance(reading, Exception):
            log.error("Fallo de sensor; quiosco fuera de servicio", exc_info=reading)
            self._do(self.checkout.fault)
            self._close_alert("quiosco fuera de servicio")
            self.sessions.finish(self._clock(), "fault")
            return
        stable = self._stability.push(reading.skus)
        if stable is not None:
            self._register_view(Counter(stable))
        self._refresh(reading.grams)

    def _register_view(self, view: Counter[str]) -> None:
        arrived = {sku: n - self._view[sku] for sku, n in view.items() if n > self._view[sku]}
        self._view = view
        if not arrived:
            return
        screen = SCREEN[self.checkout.state]  # antes de reabrir el escaneo
        # Un producto que entra a la vista en W3 reabre el escaneo: la lista confirmada
        # no puede cambiar a espaldas del cliente ni de la cámara.
        if self.checkout.state is State.CONFIRMING:
            self._do(self.checkout.correct)
        # Solo se acumulan productos registrados; los desconocidos no quedan en la lista.
        self._scanned.update(
            {sku: n for sku, n in arrived.items() if self.catalog.get(sku) is not None}
        )
        if any(self.catalog.get(sku) is None for sku in arrived):
            self._raise_alert(screen)  # conserva la auditoría para /caja, sin bloquear la webcam
        self._cart_changed()

    def _raise_alert(self, screen: str) -> None:
        """Algo que no se reconoce pasó frente a la cámara: puede salir sin pagar (no hay balanza)."""
        if self._sale_alert is not None:
            self._sale_alert["times"] += 1
            self._sale_alert["screen"] = screen
            return
        self._sale_alert = {
            "id": self._next_alert_id,
            "reason": "Producto no reconocido frente a la cámara",
            "screen": screen,
            "at": self._clock(),
            "times": 1,
            "outcome": "en curso",
        }
        self._next_alert_id += 1
        self.security_alerts.append(self._sale_alert)
        self._trim_alerts()
        log.warning("Alerta de seguridad #%d: producto no reconocido", self._sale_alert["id"])

    def _trim_alerts(self) -> None:
        """Tope de memoria sin borrar evidencia: nunca se descarta una alerta de compra pagada
        o en curso (si no, bastaría con abrir y cancelar compras para tapar una)."""
        extra = len(self.security_alerts) - MAX_PENDING
        if extra <= 0:
            return
        disposable = [a for a in self.security_alerts if a["outcome"] not in ("pagada", "en curso")]
        drop = {id(a) for a in disposable[:extra]}
        self.security_alerts = [a for a in self.security_alerts if id(a) not in drop]

    def _close_alert(self, outcome: str) -> None:
        if self._sale_alert is not None:
            self._sale_alert["outcome"] = outcome
            log.warning("Alerta de seguridad #%d: compra %s", self._sale_alert["id"], outcome)
            self._sale_alert = None

    def resolve_alert(self, alert_id: int) -> bool:
        """La caja revisó la alerta. False si no existía."""
        before = len(self.security_alerts)
        self.security_alerts = [a for a in self.security_alerts if a["id"] != alert_id]
        if self._sale_alert is not None and self._sale_alert["id"] == alert_id:
            self._sale_alert = None  # si vuelve a pasar en esta compra, la caja recibe otra alerta
        return len(self.security_alerts) < before

    def _cart(self) -> Cart:
        # En la prueba con cámara solo se cobran los productos registrados que se reconocieron.
        unknown = [] if self._close_camera is not None else [
            sku for sku in self._view.elements() if self.catalog.get(sku) is None
        ]
        return build_cart(sorted([*self._scanned.elements(), *unknown]), self.catalog)

    def _cart_changed(self) -> None:
        if self._on_cart is not None:
            self._on_cart(self._cart())

    def _refresh(self, grams: float | None) -> None:
        cart = self._cart()
        if grams is None:  # sin balanza: solo cuenta lo que reconoce la cámara
            self.checkout.update(cart, None)
            return
        self._last_grams = grams
        weight = check_weight(cart.theoretical_weight_g, grams)
        self.checkout.update(cart, weight)
        if weight.ok:
            self._mismatch_since = None
        elif self._mismatch_since is None:
            self._mismatch_since = self._clock()
        # Cuenta cada vez que la balanza detiene la compra, no cada cuadro con el peso mal.
        alarm = self._weight_alarm()
        if alarm and not self._weight_alerted:
            self.sessions.note("weight_alerts")
        self._weight_alerted = alarm

    def _weight_alarm(self) -> bool:
        since = self._mismatch_since
        return since is not None and self._clock() - since >= WEIGHT_GRACE_S

    def _poll_payment(self) -> None:
        now = self._clock()
        if self._charge is None or self._verifier is None or now - self._last_poll < POLL_EVERY_S:
            return
        self._last_poll = now
        try:
            token = self._gateway.poll(self._charge.id)
            if token is None:
                return
            event = self._verifier.verify(token)
        except PaymentError:
            log.warning("Pasarela no disponible o pago inválido", exc_info=True)
            return
        cart = self.checkout.cart
        if (
            event.charge_id != self._charge.id
            or cart is None
            or event.amount_cents != cart.total_cents
        ):
            log.warning("El pago recibido no coincide con el cobro en curso")
            return
        self._complete_sale(self._reference, self._charge.id, cart)

    def request_help(self) -> dict:
        req = {
            "id": self._next_help_id,
            "screen": SCREEN[self.checkout.state],
            "at": self._clock(),
        }
        self._next_help_id += 1
        self.help_requests.append(req)
        del self.help_requests[:-MAX_PENDING]
        self.sessions.note("help_requested")
        return req

    def resolve_help(self, help_id: int) -> bool:
        """Marca la solicitud como atendida. False si no existía (ya atendida o id inválido)."""
        before = len(self.help_requests)
        self.help_requests = [r for r in self.help_requests if r["id"] != help_id]
        return len(self.help_requests) < before

    def _alert(self) -> str | None:
        cart, weight = self.checkout.cart, self.checkout.weight
        if cart is None:
            return None
        if cart.item_count > MAX_ITEMS:
            return "Para más de 3 productos use la caja"
        if cart.unknown_skus:
            return "Hay un producto que no reconocemos"
        if weight is not None and not weight.ok and self._weight_alarm():
            return "Revise su bandeja"
        return None

    def snapshot(self) -> dict:
        c = self.checkout
        cart = c.cart
        return {
            "state": c.state.value,
            "screen": SCREEN[c.state],
            "can_pay": c.can_pay,
            "lines": [
                {
                    "sku": line.sku,
                    "name": line.name,
                    "quantity": line.quantity,
                    "unit_price_cents": line.unit_price_cents,
                }
                for line in (cart.lines if cart else ())
            ],
            "total_cents": cart.total_cents if cart else 0,
            "item_count": cart.item_count if cart else 0,
            "weight": {"ok": c.weight.ok, "diff_g": c.weight.diff_g} if c.weight else None,
            "weight_enabled": self._scale is not None,
            "camera": hasattr(self._detector, "recalibrate"),
            "alert": self._alert(),
            "seconds_in_state": round(self._clock() - self._entered_at, 1),
            "help_pending": bool(self.help_requests),
            "qr_payload": self._charge.qr_payload if self._charge else None,
            "payment_method": (
                "yape" if self._yape is not None else "yape-qr" if self._wallet_qr else "qr"
            ),
            "wallet_qr": self._wallet_qr,
            "browser_camera": self._browser_camera,
            "receipt": (
                {
                    "number": self._receipt["number"],
                    "issued_at": self._receipt["issued_at"],
                    "payer": self._payer,
                }
                if self._receipt is not None
                else None
            ),
            "payment_error": self._yape_error,
            "payment_processing": self._yape_busy,
        }
