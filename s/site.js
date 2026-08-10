/* tools/build_pages.py 가 쓴다. 손으로 고치지 말 것.
   과목 페이지에 붙는 유일한 스크립트다. 두 가지만 한다.

   1) 앱 화면에서 골라 둔 테마를 여기서도 따른다. 같은 출처라 저장소를 그대로
      읽을 수 있다. 기기가 어두워도 사람이 '밝게'를 골라 뒀으면 밝아야 한다.
   2) 앱 안에서 열렸으면 문제·정답·해설을 창구로 넘긴다. 그냥 두면 앱이 주소만
      보고 뷰어를 여는데, 그때 제목이 EBSi 원본 파일명(g_bio1_mun_3WDW7H97.pdf)이
      된다. 사람이 읽는 이름은 data-nm에 실어 두었다.

   CSP가 인라인 스크립트를 막으므로 파일로 따로 둔다. <head>에서 그냥(defer 없이)
   불러야 첫 그림 전에 테마가 걸려 화면이 번쩍이지 않는다. */
(function(){
  var KEY = "gijul.theme.v1";
  var BAR = { light:"#191713", dark:"#161A22" };
  var media = matchMedia("(prefers-color-scheme: dark)");

  function systemDark(){
    try{
      if(typeof GijulNative !== "undefined" && GijulNative && GijulNative.systemDark)
        return !!GijulNative.systemDark();
    }catch(e){}
    return media.matches;
  }

  function apply(){
    var pref = "auto";
    try{ pref = localStorage.getItem(KEY) || "auto"; }catch(e){}
    if(pref !== "light" && pref !== "dark") pref = "auto";
    var t = pref === "auto" ? (systemDark() ? "dark" : "light") : pref;
    document.documentElement.setAttribute("data-theme", t);
    var bar = document.querySelector('meta[name="theme-color"]');
    if(bar) bar.setAttribute("content", BAR[t]);
  }

  apply();
  media.addEventListener("change", apply);
  /* 앱은 액티비티를 다시 만들지 않으므로 테마가 바뀌면 이렇게 알려온다 */
  window.gijulThemeChanged = apply;
  /* 다른 탭에서 앱 화면의 테마를 바꿨을 때 */
  addEventListener("storage", function(e){ if(e.key === KEY) apply(); });

  /* 앱 안에서만 — 브라우저에서는 평범한 링크가 맞다 */
  try{
    if(typeof GijulNative === "undefined" || !GijulNative || !GijulNative.openPaper) return;
  }catch(e){ return; }
  addEventListener("click", function(e){
    var a = e.target.closest && e.target.closest(".dl a[href]");
    if(!a || e.defaultPrevented || e.button) return;
    var row = a.closest("tr");
    if(!row || !row.dataset.nm) return;
    /* 앱 화면의 fileName()과 같은 이름을 여기서 맞춘다:
       "<연도> <회차> <과목>" + " " + "문제|정답|해설" + "." + 확장자 */
    var nm = row.dataset.nm + " " + a.textContent.trim()
           + "." + a.href.split("?")[0].split(".").pop().toLowerCase();
    e.preventDefault();
    try{ GijulNative.openPaper(a.href, nm); }
    catch(err){ location.href = a.href; }
  });
})();
