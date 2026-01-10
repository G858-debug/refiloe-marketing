import React from 'react';
import { X, Check } from 'lucide-react';

interface ComparisonItem {
  text: string;
}

const beforeItems: ComparisonItem[] = [
  { text: 'Answering messages at 11pm' },
  { text: 'Chasing payments weekly' },
  { text: '2 hours per workout plan' },
  { text: 'Maxed out at 10 clients' },
  { text: 'Working weekends' },
];

const afterItems: ComparisonItem[] = [
  { text: '24/7 auto-responses' },
  { text: 'Automatic invoicing' },
  { text: 'AI plans in 2 minutes' },
  { text: 'Handle 30+ clients easily' },
  { text: 'Weekends are yours' },
];

export default function BeforeAfter() {
  return (
    <div className="w-full max-w-4xl mx-auto px-4 py-8">
      {/* Container with subtle shadow */}
      <div className="relative flex flex-col md:flex-row rounded-2xl overflow-hidden shadow-xl">

        {/* BEFORE Column */}
        <div className="flex-1 bg-[#FFF8E8] p-6 md:p-8 md:-rotate-1 md:origin-bottom-right">
          {/* Header */}
          <div className="flex items-center gap-3 mb-6">
            <div className="w-10 h-10 rounded-full bg-[#674636]/20 flex items-center justify-center">
              <span className="text-xl">😓</span>
            </div>
            <h3 className="text-2xl font-bold text-[#674636]/70">BEFORE</h3>
          </div>

          {/* Items */}
          <ul className="space-y-4">
            {beforeItems.map((item, index) => (
              <li key={index} className="flex items-start gap-3">
                <div className="flex-shrink-0 w-6 h-6 rounded-full bg-red-100 flex items-center justify-center mt-0.5">
                  <X className="w-4 h-4 text-red-500" />
                </div>
                <span className="text-[#674636]/70 text-base md:text-lg">
                  {item.text}
                </span>
              </li>
            ))}
          </ul>

          {/* Stressed illustration hint */}
          <div className="mt-6 text-center text-4xl opacity-50">
            😰
          </div>
        </div>

        {/* VS Badge - Centered between columns */}
        <div className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 z-10 hidden md:flex">
          <div className="w-14 h-14 rounded-full bg-[#674636] text-white flex items-center justify-center font-bold text-lg shadow-lg border-4 border-white">
            VS
          </div>
        </div>

        {/* Mobile VS divider */}
        <div className="md:hidden flex items-center justify-center py-4 bg-gradient-to-r from-[#FFF8E8] to-[#AAB396]">
          <div className="w-12 h-12 rounded-full bg-[#674636] text-white flex items-center justify-center font-bold shadow-lg">
            VS
          </div>
        </div>

        {/* AFTER Column */}
        <div className="flex-1 bg-[#AAB396] p-6 md:p-8 md:rotate-1 md:origin-bottom-left">
          {/* Header */}
          <div className="flex items-center gap-3 mb-6">
            <div className="w-10 h-10 rounded-full bg-white/30 flex items-center justify-center">
              <span className="text-xl">🎉</span>
            </div>
            <h3 className="text-2xl font-bold text-white">AFTER</h3>
          </div>

          {/* Items */}
          <ul className="space-y-4">
            {afterItems.map((item, index) => (
              <li key={index} className="flex items-start gap-3">
                <div className="flex-shrink-0 w-6 h-6 rounded-full bg-white/30 flex items-center justify-center mt-0.5">
                  <Check className="w-4 h-4 text-white" />
                </div>
                <span className="text-white text-base md:text-lg font-medium">
                  {item.text}
                </span>
              </li>
            ))}
          </ul>

          {/* Happy illustration hint */}
          <div className="mt-6 text-center text-4xl">
            🚀
          </div>
        </div>
      </div>

      {/* Bottom tagline */}
      <div className="mt-8 text-center">
        <p className="text-[#674636] font-semibold text-lg">
          Make the switch today
        </p>
        <p className="text-gray-600 text-sm mt-1">
          Join 317+ trainers who transformed their business
        </p>
      </div>
    </div>
  );
}
