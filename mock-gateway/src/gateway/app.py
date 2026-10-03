import hmac
from html import escape

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from gateway.charges import Charge, ChargeStore, sign_payment

PAGE = """<!doctype html>
<html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Pago simulado</title>
<style>
body {{ font-family: system-ui, sans-serif; max-width: 420px; margin: 2rem auto; padding: 0 1rem;
       text-align: center; }}
.amount {{ font-size: 2.5rem; font-weight: 700; margin: 1rem 0; }}
button {{ font-size: 1.2rem; padding: 1rem; width: 100%; border: 0; border-radius: 12px;
          background: #0f6e5c; color: #fff; }}
</style></head><body>
<p>Celular simulado · billetera de prueba</p>
<div class="amount">{amount}</div>
{body}
</body></html>"""


class ChargeIn(BaseModel):
    amount_cents: int = Field(gt=0, le=1_000_000)
    reference: str = Field(min_length=1, max_length=64)


def _soles(cents: int) -> str:
    return f"S/ {cents / 100:.2f}"


def create_app(private_key_pem: bytes, api_key: str, public_url: str) -> FastAPI:
    store = ChargeStore()
    app = FastAPI(title="mock-gateway")

    def require_key(given: str | None) -> None:
        if given is None or not hmac.compare_digest(given.encode(), api_key.encode()):
            raise HTTPException(status_code=401, detail="API key inválida")

    def find(charge_id: str) -> Charge:
        charge = store.get(charge_id)
        if charge is None:
            raise HTTPException(status_code=404, detail="Cobro no encontrado")
        return charge

    @app.post("/charges", status_code=201)
    def create_charge(body: ChargeIn, x_api_key: str | None = Header(default=None)) -> dict:
        require_key(x_api_key)
        charge = store.create(body.amount_cents, body.reference)
        return {
            "charge_id": charge.id,
            "qr_payload": f"{public_url}/pay/{charge.id}",
            "status": charge.status,
        }

    @app.get("/charges/{charge_id}")
    def get_charge(charge_id: str, x_api_key: str | None = Header(default=None)) -> dict:
        require_key(x_api_key)
        charge = find(charge_id)
        out = {"charge_id": charge.id, "status": charge.status}
        if charge.status == "PAID":
            out["token"] = sign_payment(charge, private_key_pem)
        return out

    @app.get("/pay/{charge_id}", response_class=HTMLResponse)
    def pay_page(charge_id: str) -> str:
        charge = find(charge_id)
        if charge.status == "PAID":
            body = "<p>Este cobro ya fue pagado.</p>"
        else:
            body = (
                f'<form method="post" action="/pay/{escape(charge.id)}/confirm">'
                "<button>Pagar con Yape/Plin (simulado)</button></form>"
            )
        return PAGE.format(amount=_soles(charge.amount_cents), body=body)

    @app.post("/pay/{charge_id}/confirm", response_class=HTMLResponse)
    def confirm(charge_id: str) -> str:
        charge = store.mark_paid(find(charge_id).id)
        return PAGE.format(amount=_soles(charge.amount_cents), body="<p>✅ Pago realizado</p>")

    return app
