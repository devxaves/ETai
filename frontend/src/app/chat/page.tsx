"use client";

import { useState } from "react";
import { useDropzone } from "react-dropzone";
import ChatInterface from "@/components/chat/ChatInterface";

export default function ChatPage() {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [portfolioData, setPortfolioData] = useState<any>(null);
  
  const onDrop = async (acceptedFiles: File[]) => {
    if (acceptedFiles.length === 0) return;
    
    setIsUploading(true);
    const file = acceptedFiles[0];
    const formData = new FormData();
    formData.append("file", file);
    
    try {
      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/portfolio/upload`, {
        method: 'POST',
        body: formData,
      });
      
      const data = await res.json();
      setSessionId(data.session_id);
      
      // Setup demo data payload directly for demo since we're uncoupled 
      setPortfolioData({
        healthScore: 82,
        totalValue: 582000,
        dayChange: 4200.50,
        dayChangePct: 0.72,
        allocations: [
          { name: "Large Cap", pct: 45 },
          { name: "Mid Cap", pct: 25 },
          { name: "Small Cap", pct: 15 },
          { name: "Debt/Liquid", pct: 15 },
        ]
      });
      
    } catch (err) {
      console.error("Upload failed", err);
      alert("Failed to process portfolio statement.");
    } finally {
      setIsUploading(false);
    }
  };
  
  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'text/csv': ['.csv'],
      'application/pdf': ['.pdf']
    },
    maxFiles: 1
  });

  return (
    <div className="h-full flex flex-col pt-4 px-4 overflow-hidden gap-6">
      <div className="flex justify-between items-center mb-0">
        <div>
          <h1 className="text-2xl font-black text-white tracking-tight uppercase flex items-center gap-2">
            Market Chat <span className="text-green-500">Next-Gen</span>
          </h1>
          <p className="text-[#888888] text-sm mt-1">
            ChromaDB RAG implementation providing personalized insights into your CAS/CAMS statements.
          </p>
        </div>
      </div>
      
      <div className="flex-1 flex flex-col lg:flex-row gap-6 h-[calc(100vh-140px)]">
        {/* Left Side: Portfolio / Upload */}
        <div className="w-full lg:w-5/12 h-full flex flex-col gap-6 overflow-y-auto pr-2 pb-4">
          {!sessionId ? (
            <div 
              {...getRootProps()} 
              className={`border-2 border-dashed ${isDragActive ? 'border-green-500 bg-green-500/10' : 'border-[#444] hover:border-[#666]'} rounded-xl p-12 flex flex-col items-center justify-center text-center cursor-pointer transition-colors bg-[#111]`}
            >
              <input {...getInputProps()} />
              
              {isUploading ? (
                <div className="flex flex-col items-center gap-4">
                  <div className="w-12 h-12 border-4 border-[#333] border-t-green-500 rounded-full animate-spin"></div>
                  <p className="text-white font-bold tracking-wider">INDEXING PORTFOLIO...</p>
                  <p className="text-[#888888] text-sm">Generating vector embeddings for RAG</p>
                </div>
              ) : (
                <>
                  <svg className="w-12 h-12 text-[#666] mb-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                  </svg>
                  <p className="text-lg text-white font-bold mb-2">Upload CAS / CAMS Statement</p>
                  <p className="text-sm text-[#888888] mb-6">Drag & drop your PDF or CSV file here, or click to browse</p>
                  
                  <button className="bg-[#2a2a2a] hover:bg-[#333] text-white px-6 py-2 rounded-lg font-medium transition-colors">
                    Select File
                  </button>
                  <p className="text-xs text-[#555] mt-6">All parsing occurs securely. No data is stored long-term.</p>
                </>
              )}
            </div>
          ) : (
            <>
              {/* Portfolio Health Overview */}
              <div className="bg-[#111] border border-[#2a2a2a] rounded-lg p-6 flex flex-col gap-6">
                <div className="flex justify-between items-start">
                  <div>
                    <h3 className="text-[#888] text-sm uppercase font-bold tracking-wider mb-1">Portfolio Health</h3>
                    <p className="text-4xl font-black text-white tabular-nums">{portfolioData?.healthScore}<span className="text-lg text-[#666]">/100</span></p>
                  </div>
                  
                  <div className="w-16 h-16 rounded-full border-4 border-green-500 flex items-center justify-center">
                    <span className="text-green-500 font-bold">Good</span>
                  </div>
                </div>
                
                <div className="h-px bg-[#2a2a2a] w-full"></div>
                
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <h4 className="text-[#666] text-xs font-bold uppercase mb-1">Total Value</h4>
                    <p className="text-xl font-bold text-white tabular-nums tracking-tight">
                      ₹{portfolioData?.totalValue.toLocaleString()}
                    </p>
                  </div>
                  <div>
                    <h4 className="text-[#666] text-xs font-bold uppercase mb-1">Day Change</h4>
                    <p className="text-lg font-bold text-green-400 tabular-nums">
                      +₹{portfolioData?.dayChange.toLocaleString()}
                      <span className="text-xs ml-2 bg-green-500/20 px-1 py-0.5 rounded">+{portfolioData?.dayChangePct}%</span>
                    </p>
                  </div>
                </div>
              </div>

              {/* Allocations */}
              <div className="bg-[#111] border border-[#2a2a2a] rounded-lg p-6">
                <h3 className="text-[#888] text-sm uppercase font-bold tracking-wider mb-4">Risk Allocation</h3>
                
                <div className="space-y-4">
                  {portfolioData?.allocations.map((alloc: any, i: number) => (
                    <div key={i}>
                      <div className="flex justify-between text-sm mb-1">
                        <span className="text-white font-medium">{alloc.name}</span>
                        <span className="text-[#888] font-mono">{alloc.pct}%</span>
                      </div>
                      <div className="w-full bg-[#1a1a1a] h-2 rounded-full overflow-hidden">
                        <div 
                          className="h-full bg-blue-500 rounded-full" 
                          style={{ width: `${alloc.pct}%`, opacity: 1 - (i * 0.2) }}
                        ></div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </>
          )}
        </div>

        {/* Right Side: Chat */}
        <div className="w-full lg:w-7/12 h-full pb-4 pr-1">
          <div className={`h-full opacity-100 transition-opacity duration-500 ${!sessionId ? "pointer-events-none filter blur-sm grayscale" : ""}`}>
            <ChatInterface 
              sessionId={sessionId} 
              onReset={() => {
                setSessionId(null);
                setPortfolioData(null);
              }} 
            />
          </div>
          
          {/* Overlay when disabled */}
          {!sessionId && (
            <div className="absolute inset-y-0 right-0 w-7/12 flex items-center justify-center z-10 pointer-events-none">
              <div className="bg-[#111]/80 backdrop-blur border border-[#444] text-white px-6 py-3 rounded-lg font-medium shadow-xl">
                Upload a portfolio to start chatting
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
