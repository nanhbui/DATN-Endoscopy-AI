"use client"

import { motion } from "framer-motion"
import { Button } from "@/components/ui/button"
import { Microscope } from "lucide-react"

export default function Hero() {
  return (
    <section className="relative flex min-h-[60vh] items-center justify-center bg-gradient-to-r from-cyan-600 to-blue-600 text-white mb-12">
      <motion.div
        className="text-center"
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.8 }}
      >
        <Microscope size={80} className="mx-auto mb-6" />
        <h1 className="text-5xl font-bold mb-4">Nội soi Y tế Thông minh</h1>
        <p className="text-lg mb-6 max-w-xl mx-auto">
          Nền tảng AI hỗ trợ phân tích video nội soi, phát hiện bất thường và cung cấp giải thích chi tiết.
        </p>
        <Button className="bg-white text-cyan-600 hover:bg-gray-100" onClick={() => { /* start analysis */ }}>
          Bắt đầu Phân tích
        </Button>
      </motion.div>
    </section>
  )
}
