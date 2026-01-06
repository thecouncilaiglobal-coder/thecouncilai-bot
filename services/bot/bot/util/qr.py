from __future__ import annotations

import segno


def print_qr(data: str) -> None:
    qr = segno.make(data, error='M')
    # Terminal-friendly QR
    print(qr.terminal(compact=True))
