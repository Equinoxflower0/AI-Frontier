"""
floating_home.py
================
返回首页 / 返回顶部 悬浮按钮的 HTML + JS 片段。
供 render_brief.py 和 render_index.py 共用。
"""


def render_floating_home(href: str = "index.html", label: str = "返回首页", show_after_px: int = 300) -> str:
    """
    生成右下角悬浮按钮 HTML。

    参数：
        href:  点击后跳转的地址
              - "index.html" → 跳到首页（标签页切换）
              - "#top" 或 "#" → 平滑滚到当前页顶部
        label: 按钮文字
        show_after_px: 滚动多少像素后显示按钮（避免在顶部就出现）
    """
    # 判断是跳页还是滚顶部
    is_scroll_top = href in ("#top", "#", "")

    icon_home = '''
      <svg xmlns="http://www.w3.org/2000/svg" class="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M3 12L12 3l9 9"/>
        <path d="M5 10v10h14V10"/>
      </svg>'''

    icon_arrow = '''
      <svg xmlns="http://www.w3.org/2000/svg" class="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
        <path d="M12 19V5"/>
        <path d="M5 12l7-7 7 7"/>
      </svg>'''

    icon = icon_home if not is_scroll_top else icon_arrow

    # 跳页用普通 <a>；滚顶部用 <a href="#top"> + JS 拦截做平滑滚动
    extra_js = ""
    if is_scroll_top:
        extra_js = '''
<script>
(function() {
  var btn = document.getElementById('floatingHome');
  if (!btn) return;
  btn.addEventListener('click', function(e) {
    e.preventDefault();
    window.scrollTo({ top: 0, behavior: 'smooth' });
  });
})();
</script>'''

    return f'''
<!-- 悬浮返回按钮 -->
<a href="{href}" id="floatingHome"
   class="fixed bottom-6 right-6 z-50 flex items-center gap-2 bg-gradient-to-r from-blue-600 to-indigo-600 text-white font-semibold pl-4 pr-5 py-3 rounded-full shadow-2xl shadow-blue-500/40 hover:shadow-blue-500/60 hover:scale-105 transition-all duration-200"
   style="display:none; opacity:0; transform:translateY(10px);">
  {icon}
  <span class="text-sm">{label}</span>
</a>

<script>
(function() {{
  var btn = document.getElementById('floatingHome');
  if (!btn) return;
  var threshold = {show_after_px};
  function check() {{
    if (window.scrollY > threshold) {{
      btn.style.display = 'flex';
      requestAnimationFrame(function() {{
        btn.style.opacity = '1';
        btn.style.transform = 'translateY(0)';
      }});
    }} else {{
      btn.style.opacity = '0';
      btn.style.transform = 'translateY(10px)';
      setTimeout(function() {{
        if (window.scrollY <= threshold) btn.style.display = 'none';
      }}, 250);
    }}
  }}
  window.addEventListener('scroll', check, {{ passive: true }});
  window.addEventListener('resize', check);
  setTimeout(check, 50);
}})();
</script>
{extra_js}'''