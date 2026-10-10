// Pictogramas de señalética vial dibujados como geometría: rombo de precaución, octógono de PARE,
// disco de confirmación y la bandeja con productos. Todos son decorativos (aria-hidden):
// el texto que los acompaña lleva el significado.

type Props = { className?: string };

export function CautionDiamond({ className }: Props) {
  return (
    <svg className={className} viewBox="0 0 100 100" aria-hidden="true" focusable="false">
      <rect x="15" y="15" width="70" height="70" rx="6" transform="rotate(45 50 50)" fill="var(--sign-yellow)" stroke="var(--ink)" strokeWidth="5" />
      <rect x="46" y="27" width="8" height="30" rx="3" fill="var(--ink)" />
      <circle cx="50" cy="68" r="5" fill="var(--ink)" />
    </svg>
  );
}

export function StopOctagon({ className }: Props) {
  return (
    <svg className={className} viewBox="0 0 100 100" aria-hidden="true" focusable="false">
      <polygon points="30,2 70,2 98,30 98,70 70,98 30,98 2,70 2,30" fill="var(--sign-red)" />
      <polygon points="32,7 68,7 93,32 93,68 68,93 32,93 7,68 7,32" fill="none" stroke="var(--sign-white)" strokeWidth="3" />
      <text x="50" y="61" textAnchor="middle" fontFamily="Overpass, sans-serif" fontWeight="900" fontSize="30" fill="var(--sign-white)">PARE</text>
    </svg>
  );
}

export function CheckDisc({ className }: Props) {
  return (
    <svg className={className} viewBox="0 0 100 100" aria-hidden="true" focusable="false">
      <circle cx="50" cy="50" r="46" fill="var(--ink)" />
      <path d="M28 52 L44 67 L73 35" fill="none" stroke="var(--sign-white)" strokeWidth="10" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export function ArrowRight({ className }: Props) {
  return (
    <svg className={className} viewBox="0 0 100 100" aria-hidden="true" focusable="false">
      <path d="M12 50 H78 M54 24 L82 50 L54 76" fill="none" stroke="currentColor" strokeWidth="13" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export function CameraGlyph({ className }: Props) {
  return (
    <svg className={className} viewBox="0 0 100 100" aria-hidden="true" focusable="false">
      <path d="M14 32 h16 l7 -10 h26 l7 10 h16 a6 6 0 0 1 6 6 v38 a6 6 0 0 1 -6 6 h-72 a6 6 0 0 1 -6 -6 v-38 a6 6 0 0 1 6 -6 z" fill="none" stroke="currentColor" strokeWidth="8" strokeLinejoin="round" />
      <circle cx="50" cy="56" r="14" fill="none" stroke="currentColor" strokeWidth="8" />
    </svg>
  );
}

export function RescanGlyph({ className }: Props) {
  return (
    <svg className={className} viewBox="0 0 100 100" aria-hidden="true" focusable="false">
      <path d="M80 42 A31 31 0 0 0 23 34 M20 58 A31 31 0 0 0 77 66" fill="none" stroke="currentColor" strokeWidth="9" strokeLinecap="round" />
      <path d="M82 20 V44 H58 M18 80 V56 H42" fill="none" stroke="currentColor" strokeWidth="9" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export function HelpGlyph({ className }: Props) {
  return (
    <svg className={className} viewBox="0 0 100 100" aria-hidden="true" focusable="false">
      <circle cx="50" cy="50" r="44" fill="none" stroke="currentColor" strokeWidth="9" />
      <path d="M36 38 a14 14 0 1 1 20 12.5 c-4 2 -6 5 -6 9 v3" fill="none" stroke="currentColor" strokeWidth="9" strokeLinecap="round" />
      <circle cx="50" cy="75" r="5.5" fill="currentColor" />
    </svg>
  );
}

/** Bandeja vista desde arriba con tres productos (botella, caja y bolsa), dentro del rombo amarillo. */
export function TraySign({ className, scanning = false }: Props & { scanning?: boolean }) {
  return (
    <svg className={className} viewBox="0 0 200 200" aria-hidden="true" focusable="false">
      <rect x="30" y="30" width="140" height="140" rx="12" transform="rotate(45 100 100)" fill="var(--sign-yellow)" stroke="var(--ink)" strokeWidth="8" />
      <rect x="40" y="78" width="120" height="58" rx="8" fill="none" stroke="var(--ink)" strokeWidth="7" />
      <rect x="54" y="88" width="16" height="38" rx="5" fill="var(--ink)" />
      <rect x="58" y="81" width="8" height="9" rx="2" fill="var(--ink)" />
      <rect x="80" y="96" width="30" height="30" rx="3" fill="var(--ink)" />
      <path d="M120 126 L124 96 Q135 90 146 96 L150 126 Z" fill="var(--ink)" />
      {scanning && <rect className="scan-line" x="40" y="78" width="120" height="5" fill="var(--sign-red)" />}
    </svg>
  );
}
