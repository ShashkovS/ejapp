// ESM because package.json has "type": "module"
export default {
  content: ['./index.html', './private/**/*.html', './src/**/*.{js,ts}', './private/**/*.{js,ts}'],
  theme: { extend: {} },
  plugins: [],
};
