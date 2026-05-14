from app.registry import TocallRegistry, parse_registry_json


def test_registry_parses_exact_and_wildcard_tocalls() -> None:
    entries = parse_registry_json(
        {
            "tocalls": {
                "APDW??": {"vendor": "WB2OSZ", "model": "DireWolf"},
                "APAT81": {"vendor": "AnyTone", "model": "AT-D878"},
            }
        }
    )

    registry = TocallRegistry()
    registry.entries = entries

    assert registry.lookup("APDW16") == "WB2OSZ DireWolf"
    assert registry.lookup("APAT81") == "AnyTone AT-D878"


def test_registry_supports_digit_wildcard() -> None:
    registry = TocallRegistry()
    registry.entries = {"APWnnn": "Sproul Brothers WinAPRS"}

    assert registry.lookup("APW123") == "Sproul Brothers WinAPRS"
    assert registry.lookup("APWABC") is None


def test_registry_search_resolves_exact_and_text_matches() -> None:
    registry = TocallRegistry()
    registry.entries = {
        "APDW??": "WB2OSZ DireWolf",
        "APAT81": "AnyTone AT-D878",
    }

    exact = registry.search("APDW16")
    text = registry.search("direwolf")

    assert exact[0] == {"tocall": "APDW16", "label": "WB2OSZ DireWolf", "match": "resolved"}
    assert {"tocall": "APDW??", "label": "WB2OSZ DireWolf", "match": "registry"} in exact
    assert text == [{"tocall": "APDW??", "label": "WB2OSZ DireWolf", "match": "registry"}]
