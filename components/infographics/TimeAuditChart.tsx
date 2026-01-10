import React, { useEffect, useRef, useState } from 'react';

interface TimeItem {
  icon: string;
  label: string;
  hours: number;
  percentage: number;
  color: string;
}

const timeData: TimeItem[] = [
  { icon: '💬', label: 'Client Messages', hours: 8, percentage: 35, color: 'bg-[#674636]' },
  { icon: '📋', label: 'Workout Planning', hours: 6, percentage: 26, color: 'bg-[#7D5A4A]' },
  { icon: '💰', label: 'Payment Chasing', hours: 4.5, percentage: 20, color: 'bg-[#AAB396]' },
  { icon: '📊', label: 'Progress Tracking', hours: 3, percentage: 13, color: 'bg-[#8FA37A]' },
  { icon: '📅', label: 'Scheduling', hours: 2, percentage: 9, color: 'bg-[#C4CDB4]' },
];

const TOTAL_HOURS = 23.5;

export default function TimeAuditChart() {
  const [isVisible, setIsVisible] = useState(false);
  const chartRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setIsVisible(true);
          observer.disconnect();
        }
      },
      { threshold: 0.2 }
    );

    if (chartRef.current) {
      observer.observe(chartRef.current);
    }

    return () => observer.disconnect();
  }, []);

  return (
    <div
      ref={chartRef}
      className="w-full max-w-2xl mx-auto p-6 bg-[#FFF8E8] rounded-2xl shadow-lg"
    >
      {/* Title */}
      <h2 className="text-2xl md:text-3xl font-bold text-[#674636] text-center mb-8">
        Where Does Your Time Go?
      </h2>

      {/* Bars */}
      <div className="space-y-4">
        {timeData.map((item, index) => (
          <div key={item.label} className="space-y-1">
            {/* Label row */}
            <div className="flex items-center justify-between text-sm md:text-base">
              <div className="flex items-center gap-2">
                <span className="text-xl">{item.icon}</span>
                <span className="font-medium text-[#674636]">{item.label}</span>
              </div>
              <div className="flex items-center gap-3 text-[#674636]">
                <span className="font-semibold">{item.hours}h</span>
                <span className="text-sm text-gray-500">({item.percentage}%)</span>
              </div>
            </div>

            {/* Bar */}
            <div className="h-8 bg-[#F7EED3] rounded-full overflow-hidden">
              <div
                className={`h-full ${item.color} rounded-full transition-all duration-1000 ease-out`}
                style={{
                  width: isVisible ? `${item.percentage}%` : '0%',
                  transitionDelay: `${index * 150}ms`,
                }}
              />
            </div>
          </div>
        ))}
      </div>

      {/* Total */}
      <div className="mt-8 p-4 bg-[#674636] rounded-xl text-white">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="text-2xl">⏱️</span>
            <span className="font-bold text-lg">TOTAL ADMIN TIME</span>
          </div>
          <div className="text-right">
            <span className="text-3xl font-bold">{TOTAL_HOURS}</span>
            <span className="text-xl font-medium ml-1">hours/week</span>
          </div>
        </div>
        <p className="text-sm text-[#F7EED3] mt-2 text-center">
          That's nearly a full day every week spent on tasks Refiloe can automate!
        </p>
      </div>
    </div>
  );
}
