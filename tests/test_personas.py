from app.core.enums import PersonaRole
from app.core.personas import CAST


def test_cast_covers_every_role():
    assert set(CAST) == set(PersonaRole)


def test_profile_role_matches_its_key():
    for role, profile in CAST.items():
        assert profile.role is role


def test_names_and_display_orders_are_unique():
    assert len({profile.name for profile in CAST.values()}) == len(CAST)
    assert sorted(profile.display_order for profile in CAST.values()) == [1, 2, 3, 4]


def test_accent_colors_are_hex_and_fit_the_column():
    for profile in CAST.values():
        assert profile.accent_color.startswith("#")
        # String(7) in app/models/persona.py — "#rrggbb" and nothing longer.
        assert len(profile.accent_color) == 7


def test_avatars_fit_the_column():
    for profile in CAST.values():
        assert len(profile.avatar) <= 8


def test_every_persona_has_a_system_prompt():
    for profile in CAST.values():
        assert profile.system_prompt.strip()
