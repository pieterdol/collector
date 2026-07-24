"""Junk classification: catch store clutter without eating real games."""

import pytest

from app.core.store_filters import classify


@pytest.mark.parametrize(
    "name",
    [
        "Prime Video",
        "Mediaspeler",
        "NLZIET",
        "Galaxy Common Redistributables",
        "Dragon's Dogma 2 Character Creator & Storage",
        "Concord Beta",
        "FairGame$ Playtest",
        "Resident Evil 4 Demo",
        "Ghost of Tsushima Dynamic Theme",
        "Avatar Pack: Heroes",
        "The Witcher 3 Soundtrack",
    ],
)
def test_clutter_is_flagged(name):
    assert classify(name) is not None


@pytest.mark.parametrize(
    "name",
    [
        # Real games whose titles brush against the junk patterns.
        "Ultima™ IV: Quest of the Avatar",
        "Avatar: Frontiers of Pandora",
        "Trials Fusion",
        "Alpha Protocol",
        "Beta Runner",
        "Demon's Souls",
        "Serious Sam: The Second Encounter",
        "Trine 4: The Nightmare Prince",
    ],
)
def test_real_games_survive(name):
    assert classify(name) is None


def test_store_category_marks_apps():
    assert classify("Some Streaming Thing", "media") is not None
    assert classify("Bloodborne", "ps4_game") is None
