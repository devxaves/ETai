"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import {
  ChartBarIcon,
  ChatBubbleLeftRightIcon,
  PresentationChartLineIcon,
  VideoCameraIcon,
  HomeIcon,
} from "@heroicons/react/24/outline";

const navigation = [
  { name: "Dashboard", href: "/", icon: HomeIcon },
  { name: "Opportunity Radar", href: "/radar", icon: PresentationChartLineIcon },
  { name: "Chart Intelligence", href: "/charts", icon: ChartBarIcon },
  { name: "Portfolio Chat", href: "/chat", icon: ChatBubbleLeftRightIcon },
  { name: "Video Engine", href: "/video", icon: VideoCameraIcon },
];

export default function Sidebar() {
  const pathname = usePathname();

  return (
    <div className="w-64 flex-shrink-0 bg-[#0a0a0a] border-r border-[#2a2a2a] flex flex-col h-full">
      <div className="h-16 flex items-center px-6 border-b border-[#2a2a2a]">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 bg-green-500 rounded flex items-center justify-center font-bold text-black tracking-tighter">
            ET
          </div>
          <div>
            <span className="font-bold text-white tracking-tight leading-4 block">Intelligence</span>
            <span className="text-[10px] text-[#888888] uppercase tracking-wider block">Terminal Access</span>
          </div>
        </div>
      </div>

      <nav className="flex-1 px-3 py-6 space-y-1 overflow-y-auto">
        {navigation.map((item) => {
          const isActive = pathname === item.href;
          return (
            <Link
              key={item.name}
              href={item.href}
              className={cn(
                "group flex items-center px-3 py-2.5 text-sm font-medium rounded-md transition-colors",
                isActive
                  ? "bg-[#1a1a1a] text-white border border-[#2a2a2a]"
                  : "text-[#888888] hover:bg-[#111111] border border-transparent hover:text-white"
              )}
            >
              <item.icon
                className={cn(
                  "mr-3 flex-shrink-0 h-5 w-5 transition-colors",
                  isActive ? "text-green-500" : "text-[#666666] group-hover:text-gray-300"
                )}
                aria-hidden="true"
              />
              {item.name}
              {isActive && (
                <div className="ml-auto w-1.5 h-1.5 rounded-full bg-green-500 pulse-live" />
              )}
            </Link>
          );
        })}
      </nav>

      <div className="p-4 border-t border-[#2a2a2a]">
        <div className="bg-[#1a1a1a] rounded p-3 border border-[#2a2a2a]">
          <p className="text-xs text-[#888888] mb-1">Hackathon 2026</p>
          <p className="text-[10px] text-[#666666] leading-tight">
            PS6: AI for the Indian Investor.<br/>
            Engine: Claude + Gemini + Groq
          </p>
        </div>
      </div>
    </div>
  );
}
