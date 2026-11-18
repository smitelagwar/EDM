import pytest

from edm.errors import EdmError, ErrorCode
from edm.geometry import Rect
from edm.perception.textnorm import tr_fold
from edm.win32.process import Integrity
from edm.win32.windows import WindowInfo, WindowQuery, parse_window_query, select_window


def _make_window(
    *,
    hwnd: int = 1,
    title: str = "Window",
    class_name: str = "TestClass",
    pid: int = 100,
    exe: str = "app.exe",
    z_order: int = 0,
) -> WindowInfo:
    return WindowInfo(
        hwnd=hwnd,
        title=title,
        class_name=class_name,
        pid=pid,
        exe=exe,
        rect=Rect(0, 0, 800, 600),
        minimized=False,
        maximized=False,
        visible=True,
        cloaked=False,
        topmost=False,
        foreground=z_order == 0,
        monitor_index=0,
        integrity=Integrity.medium,
        z_order=z_order,
    )


def test_parse_window_query() -> None:
    assert parse_window_query("hwnd:12") == WindowQuery(kind="hwnd", value="12")
    assert parse_window_query("pid:456") == WindowQuery(kind="pid", value="456")
    assert parse_window_query("exe:ACAD.EXE") == WindowQuery(kind="exe", value="acad.exe")
    assert parse_window_query("class:Notepad") == WindowQuery(kind="class", value="Notepad")
    assert parse_window_query("title:Adsız") == WindowQuery(kind="title", value="Adsız")
    assert parse_window_query("re:^Not.*") == WindowQuery(kind="regex", value="^Not.*")
    assert parse_window_query("autocad") == WindowQuery(kind="text", value="autocad")


@pytest.mark.parametrize("bad_query", ["", "   ", "hwnd:abc", "pid:xyz", "exe:", "re:[unclosed"])
def test_parse_window_query_invalid(bad_query: str) -> None:
    with pytest.raises(EdmError) as exc_info:
        parse_window_query(bad_query)
    assert exc_info.value.code == ErrorCode.INVALID_ARGUMENT


def test_select_prefers_topmost() -> None:
    w2 = _make_window(hwnd=20, title="Editor A", z_order=2)
    w0 = _make_window(hwnd=10, title="Editor B", z_order=0)
    w1 = _make_window(hwnd=30, title="Editor C", z_order=1)

    chosen, alts = select_window([w2, w0, w1], parse_window_query("Editor"))
    assert chosen.hwnd == 10
    assert [w.hwnd for w in alts] == [30, 20]


def test_select_not_found() -> None:
    w = _make_window(hwnd=1, title="Notepad")
    with pytest.raises(EdmError) as exc_info:
        select_window([w], parse_window_query("Calculator"))
    assert exc_info.value.code == ErrorCode.WINDOW_NOT_FOUND


def test_text_match_casefold_turkish() -> None:
    assert tr_fold("ŞÜPHE İĞNE IŞIK") == "şüphe iğne ışık"
    w = _make_window(hwnd=5, title="işlem penceresi")
    chosen, alts = select_window([w], parse_window_query("İŞLEM"))
    assert chosen.hwnd == 5
    assert alts == []


def test_select_exe_and_regex() -> None:
    w1 = _make_window(hwnd=1, title="Drawing1.dwg", exe="acad.exe", z_order=1)
    w2 = _make_window(hwnd=2, title="Not Defteri", exe="notepad.exe", z_order=0)

    chosen_exe, _ = select_window([w1, w2], parse_window_query("exe:ACAD.EXE"))
    assert chosen_exe.hwnd == 1

    chosen_re, _ = select_window([w1, w2], parse_window_query("re:^not.*"))
    assert chosen_re.hwnd == 2
