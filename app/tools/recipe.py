"""Dual-route recipe search and cooking guidance."""

from __future__ import annotations

from app.adapters.recipe_api import Recipe, SpoonacularClient, TheMealDbClient


class RecipeRouter:
    def __init__(
        self,
        spoonacular: SpoonacularClient | None,
        themealdb: TheMealDbClient,
    ) -> None:
        self.spoonacular = spoonacular
        self.themealdb = themealdb

    def search(
        self,
        ingredients: list[str],
        preferences: list[str],
        allergens: list[str],
        limit: int = 4,
    ) -> list[dict[str, object]]:
        del preferences  # Reserved for richer Spoonacular query options.
        recipes: list[Recipe] = []
        failures: list[str] = []

        if self.spoonacular is not None:
            try:
                recipes.extend(self.spoonacular.search(ingredients, limit=2))
            except Exception as exc:  # One route failing must not stop the other.
                failures.append(f"spoonacular: {exc}")

        try:
            recipes.extend(self.themealdb.search(ingredients, limit=2))
        except Exception as exc:
            failures.append(f"themealdb: {exc}")

        unique: list[Recipe] = []
        seen: set[tuple[str, str]] = set()
        for recipe in recipes:
            key = (recipe.source, recipe.id)
            if key not in seen and not self._contains_allergen(recipe, allergens):
                seen.add(key)
                unique.append(recipe)

        output = [recipe.as_dict() for recipe in unique[:limit]]
        if not output and failures:
            raise RuntimeError("Both recipe routes failed: " + " | ".join(failures))
        return output

    @staticmethod
    def _contains_allergen(recipe: Recipe, allergens: list[str]) -> bool:
        haystack = " ".join([recipe.title, recipe.instructions, *recipe.ingredients]).lower()
        return any(allergen.strip().lower() in haystack for allergen in allergens if allergen.strip())
