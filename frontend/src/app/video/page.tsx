"use client";

import { useState } from "react";
import { cn } from "@/lib/utils";

export default function VideoPage() {
  const [videoType, setVideoType] = useState("daily_wrap");
  const [period, setPeriod] = useState("today");
  
  const [isGenerating, setIsGenerating] = useState(false);
  const [jobStatus, setJobStatus] = useState<any>(null);
  const [script, setScript] = useState<string | null>(null);
  const [videoUrl, setVideoUrl] = useState<string | null>(null);

  const startGeneration = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsGenerating(true);
    setJobStatus({ progress: 5, status: "Initializing Engine..." });
    setVideoUrl(null);
    setScript(null);

    try {
      // Create job
      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/video/generate`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ type: videoType, period }),
      });
      const { job_id } = await res.json();
      
      // Poll
      const poll = setInterval(async () => {
        const statRes = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/video/status/${job_id}`);
        const statData = await statRes.json();
        
        setJobStatus(statData);
        
        if (statData.status === "completed") {
          clearInterval(poll);
          setIsGenerating(false);
          setVideoUrl(statData.video_url);
          
          // Get script
          const sRes = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/video/script/${job_id}`);
          const sData = await sRes.json();
          setScript(sData.script);
        } else if (statData.status === "failed") {
          clearInterval(poll);
          setIsGenerating(false);
        }
      }, 2000);
      
    } catch (err) {
      console.error(err);
      setIsGenerating(false);
    }
  };

  return (
    <div className="h-full flex flex-col pt-4 px-4 overflow-hidden gap-6">
      <div className="flex justify-between items-center mb-0">
        <div>
          <h1 className="text-2xl font-black text-white tracking-tight uppercase flex items-center gap-2">
            AI Video Engine <span className="text-amber-500">AutoWrap</span>
          </h1>
          <p className="text-[#888888] text-sm mt-1">
            Generates 60-second market wrap shorts using Claude for scripting and gTTS + Matplotlib for rendering.
          </p>
        </div>
      </div>
      
      <div className="flex-1 flex flex-col lg:flex-row gap-6 h-[calc(100vh-140px)]">
        {/* Controls */}
        <div className="w-full lg:w-1/3 bg-[#111111] border border-[#2a2a2a] rounded-lg p-6">
          <form onSubmit={startGeneration} className="space-y-6">
            <div>
              <label className="block text-sm font-bold text-[#888888] uppercase tracking-wide mb-2">Video Content type</label>
              <div className="space-y-3">
                {[
                  { id: "daily_wrap", title: "Daily Wrap", desc: "Nifty summary + top action" },
                  { id: "sector_rotation", title: "Sector Rotation", desc: "Heatmap + best/worst sectors" },
                  { id: "top_signals", title: "Top AI Signals", desc: "Best 3 signals from Radar" },
                ].map(opt => (
                  <div 
                    key={opt.id}
                    onClick={() => setVideoType(opt.id)}
                    className={cn(
                      "p-3 border rounded-lg cursor-pointer transition-colors",
                      videoType === opt.id ? "bg-green-500/10 border-green-500 text-white" : "bg-[#1a1a1a] border-[#2a2a2a] text-[#aaa] hover:border-[#444]"
                    )}
                  >
                    <div className="font-bold">{opt.title}</div>
                    <div className="text-xs text-[#666] mt-1">{opt.desc}</div>
                  </div>
                ))}
              </div>
            </div>
            
            <div>
              <label className="block text-sm font-bold text-[#888888] uppercase tracking-wide mb-2">Target Period</label>
              <select 
                value={period}
                onChange={e => setPeriod(e.target.value)}
                className="w-full bg-[#1a1a1a] border border-[#2a2a2a] p-3 rounded text-white focus:outline-none focus:border-green-500"
              >
                <option value="today">Today (End of Day)</option>
                <option value="this_week">This Week So Far</option>
              </select>
            </div>
            
            <button 
              type="submit" 
              disabled={isGenerating}
              className="w-full bg-green-600 hover:bg-green-500 disabled:bg-[#333] disabled:text-[#666] text-white font-bold tracking-widest uppercase p-4 rounded-lg transition-colors flex justify-center items-center gap-2"
            >
              {isGenerating ? (
                <>
                  <div className="w-4 h-4 border-2 border-white/20 border-t-white rounded-full animate-spin"></div>
                  Rendering...
                </>
              ) : (
                "Generate Short"
              )}
            </button>
          </form>
          
          {isGenerating && jobStatus && (
            <div className="mt-8 border-t border-[#2a2a2a] pt-6">
              <div className="flex justify-between text-sm mb-2">
                <span className="text-white font-mono">{jobStatus.status === "processing" ? "Agent Pipeline Running" : jobStatus.status}</span>
                <span className="text-green-400 font-bold">{jobStatus.progress || 0}%</span>
              </div>
              <div className="w-full bg-[#1a1a1a] h-2 rounded-full overflow-hidden">
                <div 
                  className="bg-green-500 h-full transition-all duration-500" 
                  style={{ width: `${jobStatus.progress || 0}%` }}
                ></div>
              </div>
              <p className="text-[#666] text-xs mt-3 italic text-center">
                Spawning background Python child processes for ffmpeg encoding...
              </p>
            </div>
          )}
        </div>
        
        {/* Output */}
        <div className="w-full lg:w-2/3 flex flex-col gap-6 h-full overflow-y-auto">
          {/* Player */}
          <div className="bg-[#111111] border border-[#2a2a2a] rounded-lg p-6 flex items-center justify-center min-h-[400px]">
             {!videoUrl ? (
               <div className="text-center">
                 <VideoCameraIcon className="w-16 h-16 text-[#333] mx-auto mb-4" />
                 <p className="text-[#666] font-medium">Video output will appear here</p>
               </div>
             ) : (
                <div className="w-full max-w-sm aspect-[9/16] bg-black border border-[#333] rounded-lg overflow-hidden relative shadow-2xl mx-auto">
                  {/* Fake video player UI since we're generating a server file */}
                  <video 
                    src={`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}${videoUrl}`} 
                    controls 
                    className="w-full h-full object-cover"
                    autoPlay
                    loop
                  >
                    Your browser doesn't support HTML video.
                  </video>
                </div>
             )}
          </div>
          
          {/* Script Viewer */}
          {script && (
            <div className="bg-[#111111] border border-[#2a2a2a] rounded-lg p-6">
              <h3 className="text-[#888] font-bold uppercase tracking-widest text-xs mb-4">Claude GENERATED SCRIPT</h3>
              <div className="prose prose-invert border-l-4 border-amber-500 pl-4 bg-[#1a1a1a] p-4 rounded-r">
                {script}
              </div>
            </div>
          )}
        </div>

      </div>
    </div>
  );
}

// Icon for placeholder
function VideoCameraIcon(props: any) {
  return (
    <svg {...props} fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" />
    </svg>
  );
}
