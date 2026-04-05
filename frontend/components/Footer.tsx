import Link from "next/link";
import { Microscope } from "lucide-react";

export default function Footer() {
  return (
    <footer className="mt-auto border-t border-white/10 bg-zinc-950/65 backdrop-blur-xl">
      <div className="mx-auto flex w-full max-w-[1440px] flex-col gap-3 px-5 py-5 text-sm text-zinc-400 lg:flex-row lg:items-center lg:justify-between lg:px-8">
        <div className="flex items-center gap-2 font-medium text-zinc-300">
          <Microscope size={16} className="text-teal-300" />
          AI Endoscopy Frontend Scaffold
        </div>
        <div className="flex items-center gap-4">
          <Link href="/workspace" className="hover:text-zinc-100 transition-colors">
            Workspace
          </Link>
          <Link href="/report" className="hover:text-zinc-100 transition-colors">
            Báo cáo
          </Link>
        </div>
        <p>© 2026 Phòng khám nội soi thông minh</p>
      </div>
    </footer>
  );
}
