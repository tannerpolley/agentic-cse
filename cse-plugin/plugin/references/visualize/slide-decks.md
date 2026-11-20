# Scientific slide decks

Use these defaults for Beamer, Quarto presentations, and PowerPoint. Follow
the deck section of the project's `STYLE.md` first, then this reference, then
generic design advice in the `pptx` skill. The project theme sets type sizes.
Use generic PowerPoint palette, dark and light slide contrast, visual motif,
and guidance about avoiding title rules and color bars only when neither a
project theme nor a brand template exists. The `pptx` skill owns PowerPoint
file validation, font substitutions, generators, and image conversion.

Read the [standing editorial decisions](../workflow/scientific-writing.md#standing-editorial-decisions)
before editing and use the shared [reader-facing identifier check](../workflow/scientific-writing.md#reader-facing-identifiers)
and [editorial compliance check](../workflow/scientific-writing.md#editorial-compliance)
at handoff.

## Audience and story

**G1. Set the audience first.** Default to a capable engineer outside the
subtopic. Identify the intended use, such as a live talk or an offline read.
Define each unfamiliar concept on an earlier slide before relying on it. Use
the simplest correct wording and a professional tone.

**G2. Make the deck stand alone.** Put definitions, base cases, and claim
limits on the slides. Speaker notes are optional.

**G3. Keep the deck at the level of the main findings.** If there is a companion
paper, leave detailed treatment there and name it once at the end. The slides
still carry the reasoning the reader needs to follow the findings.

**G4. Open with background.** Explain why the question matters. Put the main
question and its sub-questions on one early slide, answer them in order, and
connect each slide to the preceding one.
Omit an opening summary or abstract slide. For live talks, allow roughly one
main slide per presentation minute unless the speaking plan calls for a
different pace.

**G5. Put only the title and author on the cover.**

**G6. Use a short topic or question as the slide title.** Omit the final full
stop. Put the answer or observed effect in the first body line and bold it.

**G7. One message per slide.**

## Text and layout

**G8. Write short bullets and bold key terms.** Left-align body text.

**G9. Use an advisory word budget.** Aim for about 60 words on a results slide
and 80 on other slides.

**G10. Keep type and spacing consistent.** Use one body size, with at most one
smaller line for conditions. Keep title size and position the same across
content slides. Fix crowding by cutting text or splitting the slide. Keep
automatic shrink disabled.

A 16:9 Beamer page is 16 cm wide. To compare displayed text sizes with a
13.333-inch PowerPoint slide, multiply Beamer point sizes by about 2.117.
For example, 10 pt on the Beamer page displays at about the same relative size
as 20 pt on the PowerPoint slide. Use the actual canvas width for other page
sizes. For figure slots and their point sizes, follow [plotting](plotting.md#matplotlib-style-and-sizing).

**G11. Plot the quantity.** Omit oversized number callouts.

**G12. Use tables for numbers and results.** Use short cells, symbols where
clear, and only useful decimal places. Present ideas and questions as bullets.

**G13. Place text beside a figure or table by default.** Fill the available
space so text-only slides do not look half empty. Keep text clear of diagrams.

**G14. Reuse one layout for each slide type.** Use a consistent diagram style
and chart-label style throughout the deck. Highlight the current step in a
repeated process diagram, and explain the steps in the order shown.

**G15. Choose visuals that explain the result.** Use photographs of real
objects or processes when a photo is called for. Choose the figure that makes
the conclusion easiest to see.

**G16. Put sources and photo credits on one final Sources slide.**

**G17. Keep backup slides in a separate supporting deck.**

**G18. Include conditions or caveats where omitting them would lead the reader
to draw a wrong conclusion.** Preserve required scientific limits.

**G19. Check the delivered PowerPoint file itself.** Render from the actual
`.pptx` even when there is also a companion PDF.

## Deck check

Use the established [release build verification](rendering-guide.md#release-build-verification)
for build freshness, logs, and pins. For PDFs, use the
[LaTeX release sequence](latex-layout-and-qa.md#release-sequence) for geometry
and fonts. Apply the following checks to every delivery format.

1. **Render the delivered file to one image per slide.** For Beamer and Quarto
   PDFs, run [latex_visual_qa.py](../../scripts/visualize/latex_visual_qa.py) with `--profile beamer` to
   produce color and grayscale images and the overlap report. For PowerPoint,
   follow the `pptx` skill's **Converting to Images** procedure on the delivered
   file and make grayscale copies. For Quarto revealjs, export to PDF first
   and check that it represents the delivered slides. This route is unverified.
2. **Inspect every slide at full size in color and grayscale.** Prefer a
   reader who did not write the slide. Use the contact sheet only for flow and
   consistency across slides.
3. **Check each slide against G6–G10 and G13.** Count the words from extracted
   text, for example with `pdftotext -f N -l N deck.pdf -`. Look for clipped,
   overlapping, or wrapped text, uneven gaps or margins, misalignment, weak
   contrast in text or graphics, displaced template decoration, split words
   or quantities separated from their units, leftover placeholders, and
   content colliding with the footer. Check figure legibility at slide size.
4. **Check the deck's sequence and consistency.** Confirm background precedes
   the questions, answers follow the questions in order, concepts are defined
   before use, titles line up, chart labels are consistent, and Sources comes
   last.
5. **Compare the delivered formats.** Confirm that each output passed the
   applicable checks and that values match across formats.
