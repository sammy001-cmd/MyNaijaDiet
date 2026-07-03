module.exports = {
  content: ["./templates/**/*.html"],
  theme: {
    extend: {
      colors: {
        "secondary-fixed-dim": "#ffb957",
        "surface-container-highest": "#e4e2e1",
        "error-container": "#ffdad6",
        "tertiary": "#00460e",
        "inverse-on-surface": "#f3f0f0",
        "on-surface-variant": "#41493e",
        "on-secondary-container": "#694300",
        "on-tertiary": "#ffffff",
        "primary-fixed": "#acf4a4",
        "primary": "#00450d",
        "on-secondary-fixed": "#2a1800",
        "surface-container": "#f0eded",
        "on-tertiary-fixed-variant": "#005313",
        "primary-fixed-dim": "#91d78a",
        "on-tertiary-fixed": "#002204",
        "outline": "#717a6d",
        "tertiary-fixed-dim": "#7ddc7a",
        "surface-tint": "#2a6b2c",
        "on-secondary": "#ffffff",
        "primary-container": "#1b5e20",
        "on-secondary-fixed-variant": "#643f00",
        "secondary-fixed": "#ffddb5",
        "surface-container-low": "#f6f3f2",
        "on-error": "#ffffff",
        "tertiary-container": "#006017",
        "surface": "#fbf9f8",
        "tertiary-fixed": "#98f994",
        "outline-variant": "#c0c9bb",
        "secondary": "#835400",
        "on-primary-container": "#90d689",
        "secondary-container": "#fcab28",
        "inverse-surface": "#303030",
        "on-error-container": "#93000a",
        "on-primary-fixed": "#002203",
        "on-primary-fixed-variant": "#0c5216",
        "on-surface": "#1b1c1c",
        "inverse-primary": "#91d78a",
        "surface-container-high": "#eae8e7",
        "background": "#fbf9f8",
        "error": "#ba1a1a",
        "surface-dim": "#dcd9d9",
        "surface-container-lowest": "#ffffff",
        "on-background": "#1b1c1c",
        "surface-variant": "#e4e2e1",
        "surface-bright": "#fbf9f8",
        "on-tertiary-container": "#7cdb7a",
        "on-primary": "#ffffff"
      },
      borderRadius: {
        DEFAULT: "0.25rem",
        lg: "0.5rem",
        xl: "0.75rem",
        full: "9999px"
      },
      spacing: {
        "margin-mobile": "16px",
        "stack-sm": "8px",
        "gutter": "24px",
        "margin-desktop": "40px",
        "stack-md": "16px",
        "stack-lg": "32px",
        "unit": "8px",
        "container-max": "1280px"
      },
      fontFamily: {
        caption: ["Inter"],
        "headline-xl": ["Inter"],
        "label-md": ["Inter"],
        "headline-lg": ["Inter"],
        "headline-lg-mobile": ["Inter"],
        "headline-md": ["Inter"],
        "body-md": ["Inter"],
        "body-lg": ["Inter"]
      },
      fontSize: {
        caption: ["12px", { lineHeight: "16px", fontWeight: "400" }],
        "headline-xl": ["48px", { lineHeight: "56px", letterSpacing: "-0.02em", fontWeight: "800" }],
        "label-md": ["14px", { lineHeight: "20px", letterSpacing: "0.05em", fontWeight: "600" }],
        "headline-lg": ["32px", { lineHeight: "40px", letterSpacing: "-0.01em", fontWeight: "700" }],
        "headline-lg-mobile": ["28px", { lineHeight: "36px", fontWeight: "700" }],
        "headline-md": ["24px", { lineHeight: "32px", fontWeight: "600" }],
        "body-md": ["16px", { lineHeight: "24px", fontWeight: "400" }],
        "body-lg": ["18px", { lineHeight: "28px", fontWeight: "400" }]
      }
    },
  },
  plugins: [],
}

// /** @type {import('tailwindcss').Config} */
// module.exports = {
//   content: [],
//   theme: {
//     extend: {},
//   },
//   plugins: [],
// }

