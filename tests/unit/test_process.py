from edm.win32.process import Integrity, integrity_rank, self_integrity


def test_self_integrity_known() -> None:
    integrity = self_integrity()
    assert integrity != Integrity.unknown
    assert integrity in {
        Integrity.untrusted,
        Integrity.low,
        Integrity.medium,
        Integrity.high,
        Integrity.system,
    }


def test_integrity_rank_order() -> None:
    assert integrity_rank(Integrity.unknown) < integrity_rank(Integrity.untrusted)
    assert integrity_rank(Integrity.untrusted) < integrity_rank(Integrity.low)
    assert integrity_rank(Integrity.low) < integrity_rank(Integrity.medium)
    assert integrity_rank(Integrity.medium) < integrity_rank(Integrity.high)
    assert integrity_rank(Integrity.high) < integrity_rank(Integrity.system)
