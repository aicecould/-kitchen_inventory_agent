from app.adapters.recipe_api import Recipe
from app.tools.recipe import RecipeRouter


class FakeSpoonacular:
    def search(self, ingredients: list[str], limit: int = 3) -> list[Recipe]:
        assert ingredients == ["tomato"]
        return [
            Recipe(
                id="s1",
                title="Tomato salad",
                instructions="Mix tomato and salt.",
                ingredients=["tomato", "salt"],
                source="spoonacular",
            )
        ]


class FakeMealDb:
    def search(self, ingredients: list[str], limit: int = 3) -> list[Recipe]:
        return [
            Recipe(
                id="m1",
                title="Peanut tomato noodles",
                instructions="Mix peanut and tomato.",
                ingredients=["peanut", "tomato"],
                source="themealdb",
            )
        ]


def test_dual_route_filters_agent_supplied_allergen_terms() -> None:
    router = RecipeRouter(FakeSpoonacular(), FakeMealDb())  # type: ignore[arg-type]
    results = router.search(
        ingredients=["tomato"],
        preferences=[],
        allergens=["peanut"],
    )
    assert len(results) == 1
    assert results[0]["title"] == "Tomato salad"
    assert results[0]["source"] == "spoonacular"
