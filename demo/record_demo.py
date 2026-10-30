"""
Record demo/demo.webm: a guided walk through the dashboard (about 2 minutes, under the 3-minute limit).

    python3 -m pip install playwright && python3 -m playwright install chromium
    python3 demo/record_demo.py              # records the local dashboard in docs/
    python3 demo/record_demo.py https://niyogsubizo-jean-de-dieu.github.io/rwanda-yield-gap/    # or the published one

You can also record yourself with a screen recorder (e.g. Screencastify) and save as demo/demo.webm.
"""
import asyncio
import shutil
import sys
from pathlib import Path

from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parent.parent
URL = sys.argv[1] if len(sys.argv) > 1 else (ROOT / "docs" / "index.html").as_uri()
OUT = ROOT / "demo" / "demo.webm"
W, H = 1366, 768
MAP = "#map-col .tile[data-d='{}']"   # district on the (only) visible map


async def caption(pg, text):
    """Show a short on-screen caption so the video explains itself without sound."""
    await pg.evaluate("""t => { let c = document.getElementById('demo-cap');
      if (!c) { c = document.createElement('div'); c.id = 'demo-cap';
        c.style.cssText = 'position:fixed;left:50%;top:14px;transform:translateX(-50%);z-index:99;background:#0d2b4e;color:#fff;font:600 18px/1.35 sans-serif;padding:10px 18px;border-radius:10px;max-width:70%;text-align:center;box-shadow:0 4px 16px rgba(0,0,0,.25);pointer-events:none';
        document.body.appendChild(c); }
      c.textContent = t; }""", text)


async def scroll_stats(pg, y):
    """Scroll the statistics column (the window itself does not scroll on desktop)."""
    await pg.evaluate("y => document.getElementById('stats-col').scrollTo({ top: y, behavior: 'smooth' })", y)


async def main():
    tmp = ROOT / "demo" / "_video"
    shutil.rmtree(tmp, ignore_errors=True)
    async with async_playwright() as p:
        b = await p.chromium.launch()
        ctx = await b.new_context(viewport={"width": W, "height": H}, record_video_dir=str(tmp),
                                  record_video_size={"width": W, "height": H})
        await ctx.add_init_script("try { localStorage.setItem('yg-lang', 'en') } catch (e) {}")
        pg = await ctx.new_page()
        sel = lambda s, v: pg.select_option(s, v)
        wait = pg.wait_for_timeout
        await pg.goto(URL.split("#")[0] + "#trends")
        await wait(1200)

        # 1. Yield trends
        await caption(pg, "Rwanda Yield Gap Explorer: NISR survey + satellite data, 30 districts, 2017 to 2026")
        await wait(4500)
        await caption(pg, "Left: filters, a plain-language summary and the map. Right: key figures and charts")
        await wait(4500)
        await caption(pg, "Click any district on the map to select it: both columns update")
        await pg.click(MAP.format("Musanze")); await wait(3000)
        await pg.click(MAP.format("Kirehe")); await wait(2500)
        await sel("#f-base", "2019"); await wait(2500)
        await caption(pg, "The statistics column scrolls on its own: trend vs the national average and PSTA 5 target, input use")
        await scroll_stats(pg, 450); await wait(4000)
        await scroll_stats(pg, 900); await wait(3500)
        await scroll_stats(pg, 0)

        # 2. What to do
        await pg.click("a[data-tab='actions']"); await wait(1200)
        await caption(pg, "What to do: the input each district should promote, and how much extra harvest it brings")
        await wait(5000)
        await pg.click(MAP.format("Nyagatare")); await wait(3000)
        await caption(pg, "Pick one input to see where it pays off most")
        for lever in ["fertilizer", "improved_seed", "manure", "package_fert_seed_manure"]:
            await pg.click(f"button[data-lever='{lever}']"); await wait(2300)
        await pg.click("button[data-lever='best']"); await wait(800)
        await caption(pg, "Yield today and with each input, and the top 10 districts by extra harvest")
        await scroll_stats(pg, 500); await wait(4500)
        await scroll_stats(pg, 0)
        await sel("#f-crop", "Irish potato"); await wait(3500)
        await sel("#f-crop", "Maize")

        # 3. Drivers and reliability
        await pg.click("a[data-tab='drivers']"); await wait(1200)
        await caption(pg, "What drives yield: inputs and practices vs satellite weather, soil and terrain (SHAP)")
        await wait(5000)
        await sel("#f-crop", "Climbing bean"); await wait(3500)
        await sel("#f-crop", "Maize")
        await pg.click("a[data-tab='model']"); await wait(1200)
        await caption(pg, "How reliable: tested on unseen districts, an unseen year, and season by season")
        await wait(4500)
        await scroll_stats(pg, 400); await wait(3500)

        # 4. Data assistant
        await pg.click("a[data-tab='trends']"); await wait(800)
        await caption(pg, "Ask the data: an in-browser assistant that answers from the published results")
        await pg.click("#ask-btn"); await wait(1500)
        for q in ["What should Bugesera do for maize?", "How has Irish potato yield in Musanze changed since 2019?"]:
            await pg.type("#ask-in", q, delay=35); await wait(400)
            await pg.press("#ask-in", "Enter"); await wait(5000)
        await caption(pg, "'Open on map' jumps to the answer on the dashboard")
        await pg.click("#ask-log .ask-msg.bot:last-child .ask-go"); await wait(4000)
        await pg.press("#ask-in", "Escape"); await wait(800)

        # 5. Kinyarwanda + About
        await caption(pg, "Everything is available in Kinyarwanda, including the assistant")
        await pg.click("#lang-rw"); await pg.click("a[data-tab='actions']"); await wait(4500)
        await pg.click("#ask-btn"); await wait(800)
        await pg.type("#ask-in", "Ni iki kigena umusaruro w'ibigori?", delay=35); await pg.press("#ask-in", "Enter"); await wait(4500)
        await pg.press("#ask-in", "Escape")
        await pg.click("#lang-en"); await pg.click("a[data-tab='about']"); await wait(1000)
        await caption(pg, "About: data, satellite sources, the district-level data challenge, team and AI-use declaration")
        await wait(3000)
        await pg.evaluate("document.getElementById('map-col').scrollTo({ top: 900, behavior: 'smooth' })"); await wait(4000)
        video = pg.video
        await ctx.close(); await b.close()
        OUT.unlink(missing_ok=True)
        Path(await video.path()).rename(OUT)
    shutil.rmtree(tmp, ignore_errors=True)
    print(f"Saved {OUT}")


asyncio.run(main())
