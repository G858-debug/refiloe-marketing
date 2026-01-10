import React, { useEffect, useRef, useState } from 'react';

interface Stat {
  value: string;
  numericValue: number;
  suffix: string;
  label: string;
}

const stats: Stat[] = [
  { value: '317+', numericValue: 317, suffix: '+', label: 'Trainers' },
  { value: '15+', numericValue: 15, suffix: '+', label: 'Countries' },
  { value: '15+', numericValue: 15, suffix: '+', label: 'Hours Saved Weekly' },
  { value: '4.9★', numericValue: 4.9, suffix: '★', label: 'Rating' },
];

interface StatsStripProps {
  variant?: 'light' | 'dark';
  animated?: boolean;
}

export default function StatsStrip({ variant = 'light', animated = true }: StatsStripProps) {
  const [isVisible, setIsVisible] = useState(false);
  const [counts, setCounts] = useState<number[]>(stats.map(() => 0));
  const stripRef = useRef<HTMLDivElement>(null);

  const isDark = variant === 'dark';
  const bgColor = isDark ? 'bg-[#674636]' : 'bg-[#FFF8E8]';
  const textColor = isDark ? 'text-white' : 'text-[#674636]';
  const labelColor = isDark ? 'text-[#F7EED3]' : 'text-gray-600';
  const dividerColor = isDark ? 'border-[#7D5A4A]' : 'border-[#F7EED3]';

  useEffect(() => {
    if (!animated) {
      setCounts(stats.map(s => s.numericValue));
      return;
    }

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting && !isVisible) {
          setIsVisible(true);
        }
      },
      { threshold: 0.3 }
    );

    if (stripRef.current) {
      observer.observe(stripRef.current);
    }

    return () => observer.disconnect();
  }, [animated, isVisible]);

  useEffect(() => {
    if (!isVisible || !animated) return;

    const duration = 2000;
    const steps = 60;
    const interval = duration / steps;

    let step = 0;
    const timer = setInterval(() => {
      step++;
      const progress = step / steps;
      // Ease out cubic
      const eased = 1 - Math.pow(1 - progress, 3);

      setCounts(stats.map(stat => {
        const target = stat.numericValue;
        if (Number.isInteger(target)) {
          return Math.round(target * eased);
        } else {
          return Math.round(target * eased * 10) / 10;
        }
      }));

      if (step >= steps) {
        clearInterval(timer);
        setCounts(stats.map(s => s.numericValue));
      }
    }, interval);

    return () => clearInterval(timer);
  }, [isVisible, animated]);

  const formatValue = (index: number): string => {
    const stat = stats[index];
    const count = counts[index];

    if (stat.suffix === '★') {
      return count.toFixed(1) + stat.suffix;
    }
    return count + stat.suffix;
  };

  return (
    <div
      ref={stripRef}
      className={`w-full ${bgColor} py-8 md:py-10`}
    >
      <div className="max-w-4xl mx-auto px-4">
        {/* Desktop: 4 columns with dividers */}
        <div className="hidden md:grid md:grid-cols-4 md:gap-0">
          {stats.map((stat, index) => (
            <div
              key={stat.label}
              className={`text-center px-4 ${
                index < stats.length - 1 ? `border-r ${dividerColor}` : ''
              }`}
            >
              <div className={`text-4xl lg:text-5xl font-bold ${textColor}`}>
                {animated ? formatValue(index) : stat.value}
              </div>
              <div className={`mt-2 text-sm lg:text-base ${labelColor}`}>
                {stat.label}
              </div>
            </div>
          ))}
        </div>

        {/* Mobile: 2x2 grid */}
        <div className="grid grid-cols-2 gap-6 md:hidden">
          {stats.map((stat, index) => (
            <div key={stat.label} className="text-center">
              <div className={`text-3xl font-bold ${textColor}`}>
                {animated ? formatValue(index) : stat.value}
              </div>
              <div className={`mt-1 text-sm ${labelColor}`}>
                {stat.label}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
