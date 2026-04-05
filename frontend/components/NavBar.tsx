"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Activity, Gauge, Microscope, ScanLine, ScrollText } from "lucide-react";

const navItems = [
  { href: "/", label: "Dashboard", icon: Gauge },
  { href: "/workspace", label: "Workspace", icon: ScanLine },
  { href: "/report", label: "Báo cáo", icon: ScrollText },
  { href: "/train", label: "Train", icon: Activity },
];

export default function NavBar() {
  const pathname = usePathname();

  return (
    <nav className="sticky top-0 z-50 border-b border-white/10 bg-zinc-950/75 backdrop-blur-2xl">
      <div className="mx-auto flex w-full max-w-[1440px] items-center justify-between gap-4 px-5 py-3 lg:px-8">
        <Link href="/" className="flex items-center gap-3">
          <span className="inline-flex size-10 items-center justify-center rounded-xl border border-white/10 bg-zinc-900/80 text-teal-300">
            <Microscope size={20} />
          </span>
          <div>
            <p className="text-sm text-zinc-400">AI Endoscopy Suite</p>
            <p className="text-base font-semibold text-zinc-100">Hệ thống Phân tích Nội soi</p>
          </div>
        </Link>

        <ul className="flex items-center gap-2 overflow-x-auto">
          {navItems.map(({ href, label, icon: Icon }) => {
            const isActive = pathname === href;
            return (
              <li key={href}>
                <Link
                  href={href}
                  className={`inline-flex items-center gap-2 rounded-xl border px-3 py-2 text-sm transition ${
                    isActive
                      ? "border-teal-400/60 bg-teal-500/15 text-teal-200"
                      : "border-white/10 bg-zinc-900/50 text-zinc-300 hover:border-zinc-500 hover:text-zinc-100"
                  }`}
                >
                  <Icon size={16} />
                  {label}
                </Link>
              </li>
            );
          })}
        </ul>
      </div>
    </nav>
  );
}
