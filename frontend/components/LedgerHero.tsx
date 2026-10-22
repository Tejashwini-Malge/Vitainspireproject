// Original illustration, not a photo: a stack of ledger stubs under one reviewer's stamp.
// Keeps the homepage's one visual moment honest -- nothing here claims to depict a real
// NGO, donor or event, so it can never be mistaken for real activity.
export function LedgerHero() {
  return (
    <svg
      viewBox="0 0 440 420"
      role="img"
      aria-label="Three ledger stubs, stamped verified by a reviewer"
      className="w-full max-w-md"
    >
      <defs>
        <pattern id="rule" width="44" height="22" patternUnits="userSpaceOnUse">
          <line x1="0" y1="21.5" x2="44" y2="21.5" stroke="#DDD2B8" strokeWidth="1" />
        </pattern>
      </defs>

      {/* back stub */}
      <g transform="translate(18 54) rotate(-6 150 150)">
        <rect x="0" y="0" width="300" height="190" rx="3" fill="#FFFDF7" stroke="#DDD2B8" strokeWidth="1.5" />
        <rect x="0" y="0" width="300" height="190" rx="3" fill="url(#rule)" opacity="0.9" />
      </g>

      {/* middle stub */}
      <g transform="translate(70 92) rotate(4 150 95)">
        <rect x="0" y="0" width="300" height="190" rx="3" fill="#FFFDF7" stroke="#DDD2B8" strokeWidth="1.5" />
        <rect x="0" y="0" width="300" height="190" rx="3" fill="url(#rule)" opacity="0.9" />
        <rect x="18" y="18" width="130" height="10" rx="2" fill="#1D2B4F" opacity="0.85" />
        <rect x="18" y="38" width="190" height="7" rx="2" fill="#6B6355" opacity="0.5" />
        <rect x="18" y="52" width="150" height="7" rx="2" fill="#6B6355" opacity="0.5" />
        <line x1="0" y1="140" x2="300" y2="140" stroke="#DDD2B8" strokeWidth="1" strokeDasharray="4 4" />
        <circle cx="-2" cy="140" r="8" fill="#F7F1E3" stroke="#DDD2B8" />
        <circle cx="302" cy="140" r="8" fill="#F7F1E3" stroke="#DDD2B8" />
        <text x="18" y="168" fontFamily="var(--font-mono)" fontSize="13" fill="#2A2B26">
          amount -&gt; project -&gt; receipt
        </text>
      </g>

      {/* front stub, holding the stamp */}
      <g transform="translate(40 150) rotate(-2 150 115)">
        <rect x="0" y="0" width="300" height="190" rx="3" fill="#FFFDF7" stroke="#1D2B4F" strokeWidth="2" />
        <rect x="0" y="0" width="300" height="190" rx="3" fill="url(#rule)" opacity="0.9" />
        <rect x="18" y="18" width="110" height="10" rx="2" fill="#1D2B4F" opacity="0.85" />
        <rect x="18" y="38" width="170" height="7" rx="2" fill="#6B6355" opacity="0.5" />

        <g transform="translate(205 95) rotate(-12)">
          <circle cx="0" cy="0" r="58" fill="none" stroke="#1F6F4A" strokeWidth="3" />
          <circle cx="0" cy="0" r="48" fill="none" stroke="#1F6F4A" strokeWidth="1.5" />
          <path d="M -22 2 L -7 18 L 24 -16" fill="none" stroke="#1F6F4A" strokeWidth="5" strokeLinecap="round" strokeLinejoin="round" />
          <text x="0" y="-33" textAnchor="middle" fontFamily="var(--font-mono)" fontSize="11" fill="#1F6F4A" letterSpacing="2">
            VERIFIED
          </text>
          <text x="0" y="40" textAnchor="middle" fontFamily="var(--font-mono)" fontSize="8.5" fill="#1F6F4A" letterSpacing="1.5">
            BY A PERSON
          </text>
        </g>
      </g>
    </svg>
  );
}
