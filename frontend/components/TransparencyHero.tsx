"use client";

import { useRef } from "react";
import { motion, useScroll, useTransform } from "framer-motion";
import { ShieldCheck, ArrowRight, Building2 } from "lucide-react";
import Link from "next/link";
import { LedgerHero } from "@/components/LedgerHero";

/**
 * Homepage hero. Inspired by scroll-expansion hero patterns, but scoped to a bounded
 * container (useScroll with a target ref) rather than hijacking the wheel -- this is a
 * long content page people need to scroll past, not a single showcase screen.
 */
export function TransparencyHero() {
  const ref = useRef<HTMLDivElement>(null);
  const { scrollYProgress } = useScroll({ target: ref, offset: ["start start", "end start"] });

  const scale = useTransform(scrollYProgress, [0, 1], [1, 1.12]);
  const rotate = useTransform(scrollYProgress, [0, 1], [0, -2]);
  const fade = useTransform(scrollYProgress, [0, 0.8], [1, 0]);
  const lift = useTransform(scrollYProgress, [0, 1], [0, -40]);

  return (
    <section ref={ref} className="relative -mx-4 overflow-hidden px-4 pb-4 pt-2 sm:-mx-0 sm:px-0">
      <motion.div style={{ opacity: fade }} className="grid items-center gap-10 md:grid-cols-[1.1fr_0.9fr]">
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, ease: "easeOut" }}
          className="space-y-6"
        >
          <p className="inline-flex items-center gap-2 font-mono text-xs uppercase tracking-[0.18em] text-muted">
            <ShieldCheck className="h-3.5 w-3.5 text-teal" aria-hidden />
            A donation ledger, not a charity app
          </p>
          <h1 className="max-w-2xl text-4xl font-semibold leading-[1.1] tracking-tight text-navy sm:text-5xl">
            Every rupee here leaves a trail you can follow back to a person who checked it.
          </h1>
          <p className="max-w-xl text-lg text-muted">
            Below are NGOs a reviewer at Imparency has actually looked at — their registration,
            not just their website. Read about one, give if you want to, and leave. No account,
            no newsletter, no second ask.
          </p>
          <div className="flex flex-wrap gap-4 pt-2">
            <Link
              href="#ngos"
              className="group inline-flex items-center gap-2 rounded-sm bg-teal px-5 py-2.5 font-display font-medium text-paper shadow-sm transition-all hover:-translate-y-0.5 hover:shadow-md"
            >
              See who&apos;s verified
              <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5" aria-hidden />
            </Link>
            <Link
              href="/register/ngo"
              className="inline-flex items-center gap-2 rounded-sm border-2 border-navy px-5 py-2.5 font-display font-medium text-navy transition-colors hover:bg-navy hover:text-paper"
            >
              <Building2 className="h-4 w-4" aria-hidden />
              I run an NGO
            </Link>
          </div>
        </motion.div>

        <motion.div
          style={{ scale, rotate, y: lift }}
          initial={{ opacity: 0, scale: 0.92 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.7, ease: "easeOut", delay: 0.1 }}
          className="hidden justify-self-center md:flex"
        >
          <LedgerHero />
        </motion.div>
      </motion.div>
    </section>
  );
}

export default TransparencyHero;
