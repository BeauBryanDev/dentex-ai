/// <reference types="vite/client" />

// Needed explicitly because tsconfig sets `"types": ["node"]`, which stops Vite's ambient
// client types from being picked up automatically. Without this, `import icon from
// "./assets/x.svg"` has no declared type and fails to compile.
