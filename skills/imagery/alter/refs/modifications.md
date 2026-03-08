# Visual Modification Patterns

Expert techniques for modifying existing visual assets to reach desired outcomes.

## Image-to-Image (Img2Img)

**Use case:** Changing the overall style or adding global elements to an existing image while preserving the core composition.

- **Strength Parameter:** Control how much the model deviates from the original (e.g., `--strength 0.3` for subtle changes, `0.7` for drastic ones).
- **Prompting:** Focus on the *changes* you want to see, but reiterate the core elements you want to *keep*.

## Inpainting & Masking

**Use case:** Precise local edits (e.g., "Change the color of the car," "Add a person to the bench").

- **Masking:** Provide a binary mask (black and white) where white indicates the area to be changed.
- **In-place Consistency:** Use inpainting to maintain background and subject consistency while swapping specific details.

## The Review Loop: Refinement Strategies

When the output is "almost there" but not quite:

1.  **Iterative Prompting:** If a specific element is missing, increase its weight in the prompt or add specific adjectives (e.g., "vibrant emerald green" instead of just "green").
2.  **Negative Constraints:** If unwanted artifacts appear, explicitly add them to the `--negative-prompt`.
3.  **Seed Selection:** If you like the composition but want better details, fix the `--seed` and tweak only the guidance scale or prompt.
4.  **Upscaling:** Use `cstudio upscale` as the final step to bring a draft to production quality.
