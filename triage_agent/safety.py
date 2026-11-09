"""Deterministic security tripwire. The model cannot talk its way past this.

If ticket text contains a security signal, the ticket is never rated below
"high" and always goes to a human, whatever the model or injected text says.
False positives only cost a human review, which is the safe direction.
"""

SECURITY_SIGNALS = (
    # English
    "breach", "ransomware", "malware", "compromised", "phishing", "hacked",
    "intrusion", "taken over", "account takeover", "unauthorized access",
    "suspicious login", "data leak", "exfiltrat",
    # Spanish
    "intrusión", "rescate", "hackeado", "comprometid", "suplantación",
    "acceso no autorizado", "filtración",
)


def has_security_signal(text: str) -> bool:
    lowered = (text or "").lower()
    return any(signal in lowered for signal in SECURITY_SIGNALS)
