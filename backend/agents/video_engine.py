"""
agents/video_engine.py — Agent 4: AI Market Wrap Video Generator.
Generates scripts via LLM, voices via gTTS/ElevenLabs, renders via MoviePy.
"""

import asyncio
import os
import uuid
from datetime import date, datetime
from typing import Optional
import structlog

try:
    from PIL import Image
    # Pillow 10.0.0+ removed Image.ANTIALIAS; use Resampling.LANCZOS instead
    if not hasattr(Image, "ANTIALIAS"):
        if hasattr(Image, "Resampling"):
            Image.ANTIALIAS = Image.Resampling.LANCZOS
        else:
            # Fallback for very new Pillow versions
            Image.ANTIALIAS = 1  # LANCZOS constant value
except Exception:
    # Pillow not required at import time; MoviePy path handles runtime fallback.
    pass

from backend.llm_router import llm_router

logger = structlog.get_logger(__name__)

VIDEO_DIR = "/tmp/videos"
os.makedirs(VIDEO_DIR, exist_ok=True)


class VideoScript:
    """Represents a generated video script."""
    def __init__(self, title: str, narration_text: str, data_points: dict, duration_seconds: int = 60):
        self.title = title
        self.narration_text = narration_text
        self.data_points = data_points
        self.duration_seconds = duration_seconds

    def to_dict(self):
        return {
            "title": self.title, "narration_text": self.narration_text,
            "data_points": self.data_points, "duration_seconds": self.duration_seconds,
        }


class VideoScriptAgent:
    """Agent 4: Generates AI market wrap videos with narration, charts, and overlays."""

    async def generate_market_wrap_script(self, target_date: date, market_data: Optional[dict] = None) -> VideoScript:
        """
        Generate a 60-second market wrap script for a given date.

        Args:
            target_date: The trading date for the wrap.
            market_data: Optional pre-fetched market summary dict.

        Returns:
            VideoScript with title, narration, and data points.
        """
        if not market_data:
            market_data = await self._fetch_market_summary(target_date)

        nifty = market_data.get("nifty_close", 22500)
        nifty_change = market_data.get("nifty_change_pct", 0.5)
        gainers = market_data.get("top_gainers", ["TATAMOTORS", "BAJFINANCE"])
        losers = market_data.get("top_losers", ["HINDALCO", "ONGC"])
        fii_net = market_data.get("fii_net_inflow", 1200)
        top_signal = market_data.get("top_signal", "Bullish Engulfing detected on RELIANCE (82% confidence)")

        direction = "gained" if nifty_change >= 0 else "declined"
        emoji = "📈" if nifty_change >= 0 else "📉"

        prompt = f"""Generate a professional 60-second market wrap video script for {target_date.strftime('%B %d, %Y')}.

Market data:
- Nifty 50 closed at {nifty:,.0f}, {direction} {abs(nifty_change):.2f}% {emoji}
- Top gainers: {', '.join(gainers[:3])}
- Top losers: {', '.join(losers[:3])}
- FII net flow: ₹{abs(fii_net):.0f} Cr {'inflow' if fii_net >= 0 else 'outflow'}
- Top AI signal: {top_signal}

Requirements:
- Exactly 150 words (60 seconds at normal speaking pace)
- Professional financial news anchor tone
- Start with market opening tone, then key movers, then AI signal, then outlook
- End with: "Stay invested, stay informed. This was ET Investor Intelligence."
- Include 3 specific data points from the data above
- No jargon — accessible to retail investors

Return ONLY the script text, no labels or headers."""

        try:
            narration = await llm_router.complete(prompt, max_tokens=400)
        except Exception as e:
            logger.error("Script generation failed", error=str(e))
            narration = (
                f"Good evening, investors. The Nifty 50 {direction} {abs(nifty_change):.2f}% today, "
                f"closing at {nifty:,.0f}. Top performers included {', '.join(gainers[:2])}. "
                f"FII activity showed ₹{abs(fii_net):.0f} crore {'inflow' if fii_net >= 0 else 'outflow'}. "
                f"Our AI detected: {top_signal}. Stay invested, stay informed. "
                "This was ET Investor Intelligence."
            )

        title = f"ET Market Wrap — {target_date.strftime('%d %b %Y')}"

        return VideoScript(
            title=title,
            narration_text=narration.strip(),
            data_points={
                "nifty_close": nifty, "nifty_change_pct": nifty_change,
                "top_gainers": gainers, "top_losers": losers,
                "fii_net_inflow": fii_net, "date": str(target_date),
            },
            duration_seconds=60,
        )

    async def generate_video(self, script: VideoScript, job_id: Optional[str] = None) -> str:
        """
        Render the full MP4 video: voice + chart frames + text overlays.

        Args:
            script: VideoScript object.
            job_id: Optional job ID for file naming.

        Returns:
            Path to the generated MP4 file.
        """
        if job_id is None:
            job_id = str(uuid.uuid4())

        output_path = os.path.join(VIDEO_DIR, f"{job_id}.mp4")

        try:
            # Step 1: Generate voice audio
            audio_path = await self._generate_voice(script.narration_text, job_id)

            # Step 2: Generate chart frames
            chart_path = await self._generate_chart_frames(script.data_points, job_id)

            # Step 3: Stitch everything together
            final_path = await self._stitch_video(audio_path, chart_path, script, output_path)

            logger.info("Video generated", path=final_path)
            return final_path

        except Exception as e:
            logger.error("Video generation failed", error=str(e))
            # Return a simple text-only video as fallback
            return await self._generate_simple_video(script, output_path)

    async def _generate_voice(self, text: str, job_id: str) -> str:
        """Generate voice audio using gTTS or ElevenLabs."""
        from backend.config import settings
        audio_path = os.path.join(VIDEO_DIR, f"{job_id}_audio.mp3")

        # Try ElevenLabs first if key is available
        if settings.elevenlabs_api_key:
            try:
                return await self._elevenlabs_tts(text, audio_path, settings.elevenlabs_api_key)
            except Exception as e:
                logger.warning("ElevenLabs TTS failed, using gTTS", error=str(e))

        # Fallback to gTTS (free)
        return await self._gtts_tts(text, audio_path)

    async def _gtts_tts(self, text: str, output_path: str) -> str:
        """Generate audio using Google Text-to-Speech (gTTS)."""
        from gtts import gTTS

        tts = gTTS(text=text, lang="en", tld="co.in", slow=False)
        await asyncio.to_thread(tts.save, output_path)
        logger.info("gTTS audio generated", path=output_path)
        return output_path

    async def _elevenlabs_tts(self, text: str, output_path: str, api_key: str) -> str:
        """Generate premium audio using ElevenLabs API."""
        import httpx

        voice_id = "21m00Tcm4TlvDq8ikWAM"  # Rachel — professional female voice
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                url,
                headers={"xi-api-key": api_key, "Content-Type": "application/json"},
                json={"text": text, "model_id": "eleven_monolingual_v1",
                      "voice_settings": {"stability": 0.75, "similarity_boost": 0.75}},
            )
            response.raise_for_status()

        with open(output_path, "wb") as f:
            f.write(response.content)
        logger.info("ElevenLabs audio generated", path=output_path)
        return output_path

    async def _generate_chart_frames(self, data_points: dict, job_id: str) -> str:
        """Generate animated price chart using matplotlib."""
        chart_path = os.path.join(VIDEO_DIR, f"{job_id}_chart.mp4")

        def _render():
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
            import matplotlib.animation as animation
            import numpy as np

            nifty = float(data_points.get("nifty_close", 22500))
            change_pct = float(data_points.get("nifty_change_pct", 0))

            # Synthetic intraday data
            np.random.seed(42)
            prices = np.cumsum(np.random.randn(375) * 10) + (nifty - change_pct / 100 * nifty)
            prices = prices - prices[-1] + nifty

            fig, ax = plt.subplots(figsize=(12, 6))
            fig.patch.set_facecolor("#0a0a0a")
            ax.set_facecolor("#111111")
            color = "#26a69a" if change_pct >= 0 else "#ef5350"

            line, = ax.plot([], [], color=color, linewidth=2)
            ax.set_xlim(0, len(prices))
            ax.set_ylim(prices.min() * 0.999, prices.max() * 1.001)
            ax.set_title(f"Nifty 50 — {nifty:,.0f} ({'+' if change_pct >= 0 else ''}{change_pct:.2f}%)",
                         color="#e8e8e8", fontsize=14)
            ax.tick_params(colors="#888888")
            ax.spines[:].set_color("#2a2a2a")

            def update(frame):
                end = max(1, int(frame / 30 * len(prices)))
                line.set_data(range(end), prices[:end])
                return line,

            anim = animation.FuncAnimation(fig, update, frames=30, interval=100, blit=True)
            writer = animation.FFMpegWriter(fps=15, bitrate=1800)
            anim.save(chart_path, writer=writer)
            plt.close(fig)

        try:
            await asyncio.to_thread(_render)
        except Exception as e:
            logger.warning("Chart animation failed", error=str(e))
            # Create a simple still frame
            chart_path = await self._generate_still_chart(data_points, job_id)

        return chart_path

    async def _generate_still_chart(self, data_points: dict, job_id: str) -> str:
        """Fallback: generate a still image chart."""
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import numpy as np

        img_path = os.path.join(VIDEO_DIR, f"{job_id}_still.png")
        nifty = float(data_points.get("nifty_close", 22500))
        change_pct = float(data_points.get("nifty_change_pct", 0))

        fig, ax = plt.subplots(figsize=(12, 6))
        fig.patch.set_facecolor("#0a0a0a")
        ax.set_facecolor("#111111")
        color = "#26a69a" if change_pct >= 0 else "#ef5350"

        np.random.seed(42)
        prices = np.cumsum(np.random.randn(375) * 10) + nifty - change_pct / 100 * nifty
        prices = prices - prices[-1] + nifty
        ax.plot(prices, color=color, linewidth=2)
        ax.set_title(f"Nifty 50 — {nifty:,.0f}", color="#e8e8e8", fontsize=14)
        ax.set_facecolor("#111111")
        fig.savefig(img_path, facecolor="#0a0a0a", dpi=100)
        plt.close(fig)
        return img_path

    async def _stitch_video(self, audio_path: str, chart_path: str, script: VideoScript, output_path: str) -> str:
        """Combine audio and chart video into final MP4 using MoviePy."""
        def _render():
            from moviepy.editor import (
                VideoFileClip, AudioFileClip, ImageClip,
                TextClip, CompositeVideoClip, concatenate_videoclips,
            )

            duration = script.duration_seconds

            # Load chart video or image
            if chart_path.endswith(".mp4"):
                try:
                    chart_clip = VideoFileClip(chart_path).set_duration(duration)
                except Exception:
                    chart_clip = ImageClip(chart_path).set_duration(duration)
            else:
                chart_clip = ImageClip(chart_path).set_duration(duration)

            chart_clip = chart_clip.resize((1280, 720))

            # Title overlay
            try:
                title_clip = TextClip(
                    script.title, fontsize=36, color="white", font="Arial-Bold",
                    bg_color="rgba(0,0,0,0.7)", size=(1280, 80),
                ).set_duration(5).set_position(("center", 0))

                final = CompositeVideoClip([chart_clip, title_clip.set_start(0)])
            except Exception:
                final = chart_clip

            # Add audio
            if os.path.exists(audio_path):
                audio = AudioFileClip(audio_path).set_duration(duration)
                final = final.set_audio(audio)

            final.write_videofile(output_path, fps=15, codec="libx264", audio_codec="aac",
                                  logger=None, verbose=False)
            return output_path

        try:
            return await asyncio.to_thread(_render)
        except Exception as e:
            logger.error("Video stitching failed", error=str(e))
            return await self._generate_simple_video(script, output_path)

    async def _generate_simple_video(self, script: VideoScript, output_path: str) -> str:
        """Minimal fallback: just title card + audio."""
        try:
            def _render():
                import matplotlib
                matplotlib.use("Agg")
                import matplotlib.pyplot as plt
                from moviepy.editor import ImageClip, AudioFileClip, CompositeVideoClip

                fig, ax = plt.subplots(figsize=(12.8, 7.2))
                fig.patch.set_facecolor("#0a0a0a")
                ax.set_facecolor("#0a0a0a")
                ax.text(0.5, 0.6, script.title, ha="center", va="center",
                        color="#e8e8e8", fontsize=24, transform=ax.transAxes)
                ax.text(0.5, 0.4, "ET Investor Intelligence", ha="center", va="center",
                        color="#26a69a", fontsize=16, transform=ax.transAxes)
                ax.axis("off")
                img_path = output_path.replace(".mp4", "_title.png")
                fig.savefig(img_path, facecolor="#0a0a0a", dpi=100)
                plt.close(fig)

                clip = ImageClip(img_path).set_duration(script.duration_seconds)
                clip.write_videofile(output_path, fps=1, codec="libx264", logger=None, verbose=False)
                return output_path

            return await asyncio.to_thread(_render)
        except Exception as e:
            logger.error("Simple video also failed", error=str(e))
            return output_path

    async def generate_chart_animation(self, symbol: str, days: int = 30) -> str:
        """
        Create a matplotlib animation of a stock's price chart with pattern highlights.

        Args:
            symbol: NSE symbol.
            days: Number of days to animate.

        Returns:
            Path to the generated MP4 clip.
        """
        from backend.data.nse_fetcher import get_historical_ohlcv

        job_id = str(uuid.uuid4())[:8]
        output_path = os.path.join(VIDEO_DIR, f"{symbol}_{job_id}.mp4")

        df = await get_historical_ohlcv(symbol, days=days)
        if df.empty:
            return output_path

        def _render():
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
            import matplotlib.animation as animation
            import numpy as np

            prices = df["close"].values.astype(float)
            ma20 = np.convolve(prices, np.ones(min(20, len(prices))) / min(20, len(prices)), mode="valid")

            fig, ax = plt.subplots(figsize=(10, 5))
            fig.patch.set_facecolor("#0a0a0a")
            ax.set_facecolor("#111111")
            price_line, = ax.plot([], [], color="#26a69a", linewidth=2, label=symbol)
            ma_line, = ax.plot([], [], color="#f59e0b", linewidth=1, linestyle="--", label="MA20")
            ax.set_xlim(0, len(prices))
            ax.set_ylim(prices.min() * 0.98, prices.max() * 1.02)
            ax.legend(facecolor="#1a1a1a", labelcolor="#e8e8e8")
            ax.tick_params(colors="#888888")
            ax.spines[:].set_color("#2a2a2a")
            ax.set_title(f"{symbol} — {days}D Price Action", color="#e8e8e8")

            def update(frame):
                n = max(1, int(frame / 30 * len(prices)))
                price_line.set_data(range(n), prices[:n])
                ma_start = len(prices) - len(ma20)
                ma_n = max(0, n - ma_start)
                if ma_n > 0:
                    ma_line.set_data(range(ma_start, ma_start + ma_n), ma20[:ma_n])
                return price_line, ma_line,

            anim = animation.FuncAnimation(fig, update, frames=30, interval=100, blit=True)
            writer = animation.FFMpegWriter(fps=15)
            anim.save(output_path, writer=writer)
            plt.close(fig)

        try:
            await asyncio.to_thread(_render)
        except Exception as e:
            logger.error("Chart animation failed", symbol=symbol, error=str(e))

        return output_path

    async def _fetch_market_summary(self, target_date: date) -> dict:
        """Fetch market summary data for the script."""
        try:
            from backend.data.nse_fetcher import get_nifty50_quotes
            from backend.data.yfinance_fetcher import get_nifty_index
            quotes = await get_nifty50_quotes()

            gainers = [q["symbol"] for q in sorted(quotes, key=lambda x: x.get("change_pct", 0), reverse=True)[:3]]
            losers = [q["symbol"] for q in sorted(quotes, key=lambda x: x.get("change_pct", 0))[:3]]

            nifty_quote = await get_nifty_index()
            return {
                "nifty_close": nifty_quote.get("price", 22500),
                "nifty_change_pct": nifty_quote.get("change_pct", 0),
                "top_gainers": gainers, "top_losers": losers,
                "fii_net_inflow": 1200,  # Fetched separately in production
                "top_signal": "Bullish Engulfing on RELIANCE (82% confidence)",
            }
        except Exception as e:
            logger.warning("Market summary fetch failed", error=str(e))
            return {
                "nifty_close": 22500, "nifty_change_pct": 0.45,
                "top_gainers": ["TATAMOTORS", "BAJFINANCE", "TCS"],
                "top_losers": ["HINDALCO", "ONGC", "BPCL"],
                "fii_net_inflow": 1200,
                "top_signal": "Bullish momentum detected across IT sector",
            }
