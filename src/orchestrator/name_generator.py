"""Funny name generator for Madrox instances."""

import secrets


class NameGenerator:
    """Generate funny random names for instances."""

    # Adjectives that create funny combinations
    ADJECTIVES = [
        "Sneaky", "Bouncy", "Giggly", "Wobbly", "Zesty", "Quirky", "Sassy",
        "Grumpy", "Bubbly", "Dizzy", "Fuzzy", "Jolly", "Mighty", "Silly",
        "Spunky", "Witty", "Chunky", "Peppy", "Cranky", "Perky", "Wacky",
        "Zippy", "Goofy", "Snazzy", "Funky", "Cheesy", "Jazzy", "Plucky",
        "Cheeky", "Dopey", "Frisky", "Groovy", "Lanky", "Nerdy", "Punky",
        "Rowdy", "Scrappy", "Sleepy", "Sloppy", "Snappy", "Sparkly", "Speedy",
        "Spicy", "Stubby", "Swanky", "Tipsy", "Twitchy", "Whimsical", "Wonky",
        "Zany", "Bashful", "Clumsy", "Dapper", "Feisty", "Fluffy", "Hasty",
        "Jittery", "Loopy", "Muddy", "Nutty", "Peachy", "Prickly", "Puffy",
        "Rusty", "Salty", "Scruffy", "Shiny", "Slippery", "Squishy", "Stinky",
        "Tangy", "Toasty", "Wiggly", "Wrinkly", "Yummy", "Zingy", "Bonkers",
        "Crunchy", "Derpy", "Flaky", "Groggy", "Hipster", "Jiggly", "Kooky"
    ]

    # Nouns that pair well with the adjectives
    NOUNS = [
        "Pickle", "Noodle", "Muffin", "Waffle", "Taco", "Burrito", "Donut",
        "Cupcake", "Pancake", "Biscuit", "Cookie", "Pretzel", "Bagel", "Toast",
        "Banana", "Potato", "Tomato", "Avocado", "Mango", "Coconut", "Pumpkin",
        "Penguin", "Platypus", "Llama", "Alpaca", "Koala", "Sloth", "Panda",
        "Narwhal", "Walrus", "Hamster", "Gopher", "Beaver", "Otter", "Ferret",
        "Hedgehog", "Armadillo", "Mongoose", "Lemur", "Capybara", "Wombat",
        "Quokka", "Axolotl", "Chinchilla", "Gecko", "Iguana", "Tortoise",
        "Wizard", "Pirate", "Ninja", "Viking", "Robot", "Zombie", "Vampire",
        "Dragon", "Unicorn", "Phoenix", "Griffin", "Kraken", "Yeti", "Goblin",
        "Sprite", "Gnome", "Troll", "Ogre", "Leprechaun", "Sasquatch", "Alien",
        "Hobbit", "Warlock", "Knight", "Jester", "Bard", "Rogue", "Paladin",
        "Sock", "Bucket", "Spoon", "Fork", "Spatula", "Whisk", "Ladle",
        "Kazoo", "Ukulele", "Bongo", "Accordion", "Tuba", "Harmonica", "Banjo",
        "Gadget", "Gizmo", "Widget", "Doodad", "Thingamajig", "Doohickey"
    ]

    # Titles/prefixes for extra funniness (optional)
    TITLES = [
        "Captain", "Professor", "Doctor", "Admiral", "General", "Major",
        "Sir", "Lady", "Lord", "Duke", "Count", "Baron", "Agent",
        "Detective", "Inspector", "Sergeant", "Chief", "Master", "Grand"
    ]

    def __init__(self):
        """Initialize the name generator."""
        self.used_names = set()

    def generate(self, include_title: bool = False) -> str:
        """Generate a unique funny name.

        Args:
            include_title: Whether to include a title prefix (10% chance by default)

        Returns:
            A unique funny name like "Sneaky-Pickle" or "Captain-Wobbly-Noodle"
        """
        max_attempts = 100

        for _ in range(max_attempts):
            # Randomly decide whether to include a title (10% chance)
            if include_title or (secrets.randbelow(10) < 1):
                title = secrets.choice(self.TITLES)
                adjective = secrets.choice(self.ADJECTIVES)
                noun = secrets.choice(self.NOUNS)
                name = f"{title}-{adjective}-{noun}"
            else:
                adjective = secrets.choice(self.ADJECTIVES)
                noun = secrets.choice(self.NOUNS)
                name = f"{adjective}-{noun}"

            # Check if name is unique
            if name not in self.used_names:
                self.used_names.add(name)
                return name

        # Fallback: add a number if we can't find a unique name
        base_name = f"{secrets.choice(self.ADJECTIVES)}-{secrets.choice(self.NOUNS)}"
        counter = 1
        while f"{base_name}-{counter}" in self.used_names:
            counter += 1

        name = f"{base_name}-{counter}"
        self.used_names.add(name)
        return name

    def is_valid_custom_name(self, name: str) -> bool:
        """Check if a custom name is valid.

        Args:
            name: The custom name to validate

        Returns:
            True if the name is valid and available
        """
        # Check basic validity
        if not name or len(name) < 1 or len(name) > 100:
            return False

        # Check if already used
        if name in self.used_names:
            return False

        return True

    def register_custom_name(self, name: str) -> bool:
        """Register a custom name as used.

        Args:
            name: The custom name to register

        Returns:
            True if successfully registered
        """
        if self.is_valid_custom_name(name):
            self.used_names.add(name)
            return True
        return False


# Global instance for the application
name_generator = NameGenerator()


def get_instance_name(custom_name: str | None = None) -> str:
    """Get a name for an instance.

    Args:
        custom_name: Optional custom name. If not provided or invalid, generates a funny name.

    Returns:
        The instance name to use
    """
    if custom_name:
        # Clean the custom name
        custom_name = custom_name.strip()

        # If it's a valid custom name, use it
        if name_generator.is_valid_custom_name(custom_name):
            name_generator.register_custom_name(custom_name)
            return custom_name

        # If custom name is taken, append a funny suffix
        funny_suffix = name_generator.generate()
        combined_name = f"{custom_name}-aka-{funny_suffix}"
        name_generator.register_custom_name(combined_name)
        return combined_name

    # Generate a funny name
    return name_generator.generate()
