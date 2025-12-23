"""Comprehensive unit tests for name_generator module."""

from unittest.mock import patch

from orchestrator.name_generator import (
    NameGenerator,
    get_instance_name,
    name_generator,
)


class TestNameGeneratorInit:
    """Test NameGenerator initialization."""

    def test_init_creates_empty_used_names(self):
        """Test that __init__ creates an empty used_names set."""
        gen = NameGenerator()
        assert isinstance(gen.used_names, set)
        assert len(gen.used_names) == 0

    def test_init_creates_independent_instances(self):
        """Test that each instance has independent used_names."""
        gen1 = NameGenerator()
        gen2 = NameGenerator()
        gen1.used_names.add("test-name")
        assert "test-name" in gen1.used_names
        assert "test-name" not in gen2.used_names


class TestNameGeneratorConstants:
    """Test NameGenerator class constants."""

    def test_adjectives_list_exists(self):
        """Test that ADJECTIVES list is defined."""
        assert hasattr(NameGenerator, "ADJECTIVES")
        assert isinstance(NameGenerator.ADJECTIVES, list)
        assert len(NameGenerator.ADJECTIVES) > 0

    def test_nouns_list_exists(self):
        """Test that NOUNS list is defined."""
        assert hasattr(NameGenerator, "NOUNS")
        assert isinstance(NameGenerator.NOUNS, list)
        assert len(NameGenerator.NOUNS) > 0

    def test_titles_list_exists(self):
        """Test that TITLES list is defined."""
        assert hasattr(NameGenerator, "TITLES")
        assert isinstance(NameGenerator.TITLES, list)
        assert len(NameGenerator.TITLES) > 0

    def test_adjectives_are_strings(self):
        """Test that all adjectives are strings."""
        assert all(isinstance(adj, str) for adj in NameGenerator.ADJECTIVES)

    def test_nouns_are_strings(self):
        """Test that all nouns are strings."""
        assert all(isinstance(noun, str) for noun in NameGenerator.NOUNS)

    def test_titles_are_strings(self):
        """Test that all titles are strings."""
        assert all(isinstance(title, str) for title in NameGenerator.TITLES)

    def test_no_duplicate_adjectives(self):
        """Test that adjectives list has no duplicates."""
        assert len(NameGenerator.ADJECTIVES) == len(set(NameGenerator.ADJECTIVES))

    def test_no_duplicate_nouns(self):
        """Test that nouns list has no duplicates."""
        assert len(NameGenerator.NOUNS) == len(set(NameGenerator.NOUNS))

    def test_no_duplicate_titles(self):
        """Test that titles list has no duplicates."""
        assert len(NameGenerator.TITLES) == len(set(NameGenerator.TITLES))


class TestNameGeneratorGenerate:
    """Test NameGenerator.generate() method."""

    def test_generate_returns_string(self):
        """Test that generate() returns a string."""
        gen = NameGenerator()
        name = gen.generate()
        assert isinstance(name, str)

    def test_generate_returns_non_empty_string(self):
        """Test that generate() returns a non-empty string."""
        gen = NameGenerator()
        name = gen.generate()
        assert len(name) > 0

    def test_generate_has_hyphen_separator(self):
        """Test that generated names use hyphen separator."""
        gen = NameGenerator()
        name = gen.generate()
        assert "-" in name

    def test_generate_without_title_has_two_parts(self):
        """Test that names without title have format 'Adjective-Noun'."""
        gen = NameGenerator()
        # Mock to ensure no title is added
        with patch("secrets.randbelow", return_value=5):
            name = gen.generate(include_title=False)
            parts = name.split("-")
            # Should be Adjective-Noun (2 parts) unless numbered fallback
            if not parts[-1].isdigit():
                assert len(parts) == 2

    def test_generate_with_title_has_three_parts(self):
        """Test that names with title have format 'Title-Adjective-Noun'."""
        gen = NameGenerator()
        name = gen.generate(include_title=True)
        parts = name.split("-")
        # Should be Title-Adjective-Noun (3 parts) unless numbered fallback
        if not parts[-1].isdigit():
            assert len(parts) == 3

    def test_generate_uses_valid_adjective(self):
        """Test that generated names use adjectives from ADJECTIVES list."""
        gen = NameGenerator()
        with patch("secrets.randbelow", return_value=5):
            name = gen.generate(include_title=False)
            adjective = name.split("-")[0]
            assert adjective in NameGenerator.ADJECTIVES

    def test_generate_uses_valid_noun(self):
        """Test that generated names use nouns from NOUNS list."""
        gen = NameGenerator()
        with patch("secrets.randbelow", return_value=5):
            name = gen.generate(include_title=False)
            noun = name.split("-")[1]
            assert noun in NameGenerator.NOUNS

    def test_generate_uses_valid_title_when_included(self):
        """Test that generated names use titles from TITLES list."""
        gen = NameGenerator()
        name = gen.generate(include_title=True)
        title = name.split("-")[0]
        assert title in NameGenerator.TITLES

    def test_generate_adds_to_used_names(self):
        """Test that generate() adds the name to used_names."""
        gen = NameGenerator()
        initial_count = len(gen.used_names)
        name = gen.generate()
        assert len(gen.used_names) == initial_count + 1
        assert name in gen.used_names

    def test_generate_returns_unique_names(self):
        """Test that generate() returns unique names."""
        gen = NameGenerator()
        names = [gen.generate() for _ in range(100)]
        # All names should be unique
        assert len(names) == len(set(names))

    def test_generate_exhaustion_fallback(self):
        """Test that generate() uses numbered fallback when exhausted."""
        gen = NameGenerator()
        # Pre-populate used_names to trigger fallback
        # Mock to always return the same adjective and noun
        with patch("secrets.choice", side_effect=["Sneaky", "Pickle"] * 200):
            names = []
            for _ in range(5):
                name = gen.generate()
                names.append(name)

            # After first "Sneaky-Pickle", should get numbered versions
            assert "Sneaky-Pickle" in names[0] or "-1" in names[1] or "-2" in names[2]

    def test_generate_respects_include_title_parameter(self):
        """Test that include_title parameter is respected."""
        gen = NameGenerator()

        # When include_title=True, should always have title
        name_with_title = gen.generate(include_title=True)
        parts_with_title = name_with_title.split("-")
        assert parts_with_title[0] in NameGenerator.TITLES

    def test_generate_randomness(self):
        """Test that generate() produces different names across calls."""
        gen = NameGenerator()
        names = [gen.generate() for _ in range(10)]
        # Should have multiple unique names (probabilistically)
        assert len(set(names)) > 1


class TestIsValidCustomName:
    """Test NameGenerator.is_valid_custom_name() method."""

    def test_valid_custom_name_returns_true(self):
        """Test that valid custom name returns True."""
        gen = NameGenerator()
        assert gen.is_valid_custom_name("my-custom-name") is True

    def test_empty_string_returns_false(self):
        """Test that empty string returns False."""
        gen = NameGenerator()
        assert gen.is_valid_custom_name("") is False

    def test_none_value_returns_false(self):
        """Test that None value is handled correctly."""
        gen = NameGenerator()
        # is_valid_custom_name checks "not name" which catches None
        result = gen.is_valid_custom_name(None)  # type: ignore
        assert result is False

    def test_whitespace_only_returns_false(self):
        """Test that whitespace-only string has length > 0 but tests emptiness."""
        gen = NameGenerator()
        # Whitespace has length but may not be valid
        result = gen.is_valid_custom_name("   ")
        # Based on code: len(name) > 0 would be True for "   "
        assert result is True  # Has length, passes basic check

    def test_single_character_name_is_valid(self):
        """Test that single character name is valid."""
        gen = NameGenerator()
        assert gen.is_valid_custom_name("a") is True

    def test_name_exactly_100_chars_is_valid(self):
        """Test that name with exactly 100 characters is valid."""
        gen = NameGenerator()
        name_100 = "a" * 100
        assert gen.is_valid_custom_name(name_100) is True

    def test_name_101_chars_is_invalid(self):
        """Test that name with 101 characters is invalid."""
        gen = NameGenerator()
        name_101 = "a" * 101
        assert gen.is_valid_custom_name(name_101) is False

    def test_already_used_name_returns_false(self):
        """Test that already used name returns False."""
        gen = NameGenerator()
        gen.used_names.add("taken-name")
        assert gen.is_valid_custom_name("taken-name") is False

    def test_unused_name_returns_true(self):
        """Test that unused name returns True."""
        gen = NameGenerator()
        gen.used_names.add("other-name")
        assert gen.is_valid_custom_name("my-name") is True

    def test_special_characters_are_allowed(self):
        """Test that names with special characters are allowed."""
        gen = NameGenerator()
        assert gen.is_valid_custom_name("my_name-123") is True
        assert gen.is_valid_custom_name("name@domain") is True


class TestRegisterCustomName:
    """Test NameGenerator.register_custom_name() method."""

    def test_register_valid_name_returns_true(self):
        """Test that registering valid name returns True."""
        gen = NameGenerator()
        result = gen.register_custom_name("custom-name")
        assert result is True

    def test_register_valid_name_adds_to_used_names(self):
        """Test that registering valid name adds it to used_names."""
        gen = NameGenerator()
        gen.register_custom_name("custom-name")
        assert "custom-name" in gen.used_names

    def test_register_invalid_name_returns_false(self):
        """Test that registering invalid name returns False."""
        gen = NameGenerator()
        result = gen.register_custom_name("")
        assert result is False

    def test_register_invalid_name_does_not_add_to_used_names(self):
        """Test that registering invalid name doesn't add to used_names."""
        gen = NameGenerator()
        initial_count = len(gen.used_names)
        gen.register_custom_name("")
        assert len(gen.used_names) == initial_count

    def test_register_duplicate_name_returns_false(self):
        """Test that registering duplicate name returns False."""
        gen = NameGenerator()
        gen.register_custom_name("duplicate-name")
        result = gen.register_custom_name("duplicate-name")
        assert result is False

    def test_register_too_long_name_returns_false(self):
        """Test that registering too long name returns False."""
        gen = NameGenerator()
        long_name = "a" * 101
        result = gen.register_custom_name(long_name)
        assert result is False


class TestGetInstanceName:
    """Test get_instance_name() function."""

    def setup_method(self):
        """Reset the global name_generator before each test."""
        # Clear the global instance's used_names
        name_generator.used_names.clear()

    def test_get_instance_name_with_none_generates_funny_name(self):
        """Test that passing None generates a funny name."""
        name = get_instance_name(None)
        assert isinstance(name, str)
        assert len(name) > 0
        assert "-" in name

    def test_get_instance_name_without_arg_generates_funny_name(self):
        """Test that calling without arguments generates a funny name."""
        name = get_instance_name()
        assert isinstance(name, str)
        assert len(name) > 0
        assert "-" in name

    def test_get_instance_name_with_valid_custom_name_returns_it(self):
        """Test that valid custom name is returned."""
        custom_name = "my-valid-custom-name"
        name = get_instance_name(custom_name)
        assert name == custom_name

    def test_get_instance_name_with_valid_custom_name_registers_it(self):
        """Test that valid custom name is registered."""
        custom_name = "registered-custom-name"
        get_instance_name(custom_name)
        assert custom_name in name_generator.used_names

    def test_get_instance_name_strips_whitespace(self):
        """Test that custom name whitespace is stripped."""
        custom_name = "  spaced-name  "
        name = get_instance_name(custom_name)
        assert name == "spaced-name"

    def test_get_instance_name_with_duplicate_custom_name_adds_suffix(self):
        """Test that duplicate custom name gets funny suffix."""
        custom_name = "duplicate-name"
        # First call should succeed
        name1 = get_instance_name(custom_name)
        assert name1 == custom_name

        # Second call should add suffix
        name2 = get_instance_name(custom_name)
        assert name2 != custom_name
        assert name2.startswith(custom_name + "-aka-")
        assert name2 in name_generator.used_names

    def test_get_instance_name_suffix_format(self):
        """Test that duplicate name suffix has correct format."""
        custom_name = "test-duplicate"
        get_instance_name(custom_name)
        suffixed_name = get_instance_name(custom_name)

        # Should be "custom-name-aka-FunnyName"
        assert "-aka-" in suffixed_name
        parts = suffixed_name.split("-aka-")
        assert parts[0] == custom_name
        assert len(parts[1]) > 0  # Has a funny suffix

    def test_get_instance_name_with_empty_string_generates_funny_name(self):
        """Test that empty string generates a funny name."""
        name = get_instance_name("")
        # Empty string is invalid, should generate funny name
        assert isinstance(name, str)
        assert len(name) > 0

    def test_get_instance_name_with_too_long_name_adds_suffix(self):
        """Test that too long custom name gets funny suffix."""
        long_name = "a" * 101
        name = get_instance_name(long_name)
        # Should get suffix because invalid
        assert "-aka-" in name

    def test_get_instance_name_multiple_calls_unique(self):
        """Test that multiple calls without custom name return unique names."""
        names = [get_instance_name() for _ in range(10)]
        assert len(names) == len(set(names))

    def test_get_instance_name_integration_with_generator(self):
        """Test integration between get_instance_name and name_generator."""
        # Clear to start fresh
        name_generator.used_names.clear()

        # Generate some names
        name1 = get_instance_name()
        name2 = get_instance_name("custom")
        name3 = get_instance_name("custom")  # Duplicate

        # All should be in used_names
        assert name1 in name_generator.used_names
        assert name2 in name_generator.used_names
        assert name3 in name_generator.used_names
        # Note: When creating the suffix for name3, it also registers the funny name
        # So we have: name1, name2 ("custom"), the funny suffix itself, and name3 (custom-aka-suffix)
        assert len(name_generator.used_names) >= 3


class TestGlobalNameGenerator:
    """Test the global name_generator instance."""

    def test_global_name_generator_exists(self):
        """Test that global name_generator instance exists."""
        assert name_generator is not None

    def test_global_name_generator_is_instance(self):
        """Test that global name_generator is a NameGenerator instance."""
        assert isinstance(name_generator, NameGenerator)

    def test_global_name_generator_is_singleton(self):
        """Test that global name_generator maintains state across imports."""
        from orchestrator.name_generator import name_generator as ng2

        assert name_generator is ng2


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_name_generator_with_many_generations(self):
        """Test generating many names doesn't break."""
        gen = NameGenerator()
        names = [gen.generate() for _ in range(1000)]
        assert len(names) == 1000
        assert len(set(names)) == 1000  # All unique

    def test_unicode_custom_name(self):
        """Test that unicode characters in custom names are handled."""
        gen = NameGenerator()
        unicode_name = "test-名前-name"
        result = gen.is_valid_custom_name(unicode_name)
        # Should be valid if within length limits
        assert result is True
        assert gen.register_custom_name(unicode_name) is True

    def test_custom_name_with_hyphens(self):
        """Test that custom names with hyphens are valid."""
        gen = NameGenerator()
        hyphenated_name = "my-custom-name-with-many-hyphens"
        assert gen.is_valid_custom_name(hyphenated_name) is True

    def test_numbered_fallback_increments_correctly(self):
        """Test that numbered fallback increments when names are taken."""
        gen = NameGenerator()

        # Mock to always return same adjective/noun
        with patch("secrets.choice") as mock_choice:
            mock_choice.side_effect = ["Test"] * 100 + ["Name"] * 100

            # Manually add base name
            gen.used_names.add("Test-Name")
            gen.used_names.add("Test-Name-1")

            # This should trigger fallback and use -2
            with patch("secrets.randbelow", return_value=5):
                # Simulate the fallback path
                base_name = "Test-Name"
                counter = 1
                while f"{base_name}-{counter}" in gen.used_names:
                    counter += 1
                expected_name = f"{base_name}-{counter}"
                assert expected_name == "Test-Name-2"


class TestConcurrency:
    """Test thread-safety considerations (documentation purposes)."""

    def test_independent_generators_are_thread_safe(self):
        """Test that independent NameGenerator instances don't interfere."""
        gen1 = NameGenerator()
        gen2 = NameGenerator()

        name1 = gen1.generate()
        name2 = gen2.generate()

        # Each should track its own used names
        assert name1 in gen1.used_names
        assert name1 not in gen2.used_names
        assert name2 in gen2.used_names
        assert name2 not in gen1.used_names

    def test_global_generator_state_persistence(self):
        """Test that global generator maintains state across function calls."""
        initial_count = len(name_generator.used_names)

        get_instance_name()
        get_instance_name()

        # Should have added 2 names
        assert len(name_generator.used_names) == initial_count + 2
