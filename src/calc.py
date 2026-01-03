def add(a, b):
    """Return the sum of two numbers; reject non-numeric inputs."""
    if not isinstance(a, (int, float)) or not isinstance(b, (int, float)):
        raise TypeError("add expects numeric inputs")
    return a + b
