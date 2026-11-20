# ORAYA light editorial design system

Primary reference: the light ORAYA image supplied by the user. Shared identity: warm paper, forest ink, coral actions, restrained botanical/educational artwork and generous editorial type. The landing is built from SVG, CSS and real UI elements; screenshots are QA evidence only.

- Background: warm ivory `#fcf8f1`; authenticated canvas `#f9f6ef`.
- Navigation/sage surfaces: `#f2f1e7`, `#e9eddf`.
- Ink: `#252b24`; forest `#294536`.
- Coral: `#e9694e` / app `#dc7258`; hover `#bf5a42`.
- Journey colours: peach `#fae1d1`, sage `#e8ead8`, blue `#e0ebf1`, lavender `#eee3ef`.
- Display: Instrument Serif, with Georgia fallback. Body/UI: DM Sans, with system sans fallback. Avoid synthesized serif bold.
- App surfaces use fine borders, small radii, minimal shadow, and distinct section compositions. Round pill shapes are reserved primarily for landing actions and filters.
- Desktop shell: fixed 235 px sidebar with grouped learning journey and a compact profile header. Mobile: a collapsible sidebar, Escape dismissal, hidden closed links and a skip-to-content link.
- Spatial scenes alone use atmospheric deep green for object contrast; their surrounding app remains light.
- Motion: subtle floating SVG objects and hover responses. Respect `prefers-reduced-motion`. Static 3D scenes render on input, resize and selection, avoiding idle animation loops.
- Source content is selectable. Highlights, notes and cards persist on the backend. Empty states use accurate counts and a concrete next step, never invented student progress.
- Use accessible labels, visible focus and semantic forms. Shared widgets remain keyboard-accessible; spatial object lists provide text alternatives to canvas selection.

The landing, auth, shell, reader, exams, rooms, comparison, memory and spatial layouts have bespoke styling. Some retained feature-page internals still require a deeper composition pass; see the completion matrix.
