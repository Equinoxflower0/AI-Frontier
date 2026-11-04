/** @type {import('tailwindcss').Config} */
module.exports = {
  // 扫描所有已生成的静态页面，按实际出现的 class 生成 CSS
  content: [
    "./*.html",
    "./tutorials/*.html",
    "./scripts/render_*.py",
  ],
  theme: {
    extend: {},
  },
  // 运行时拼接出来的类名，静态扫描无法发现，必须显式列入白名单。
  // 对应 playground.html 中：'bg-' + (type/diff/...) + '-200'
  safelist: [
    "bg-indigo-200",
    "bg-emerald-200",
    "bg-amber-200",
    "font-bold",
  ],
  plugins: [],
};
