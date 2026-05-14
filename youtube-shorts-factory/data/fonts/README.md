# Fonts

Drop your caption font(s) here.

The default config uses **Montserrat Black** (`Montserrat-Black.ttf`).
Download it free from Google Fonts:

  https://fonts.google.com/specimen/Montserrat

The factory will fail at the caption-render step if `Montserrat-Black.ttf`
is missing. To use a different font, update `captions.style.font` and
`thumbnail.title_font` in `config.yaml` and place the corresponding
`.ttf` file in this folder.

The Docker image only installs DejaVu by default — you must mount this
folder (or COPY a font in) for production.
