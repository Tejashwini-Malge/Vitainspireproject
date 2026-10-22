"use client";

import Link from "next/link";
import { useState } from "react";

type RegType = "ngo" | "donor" | null;

export default function RegisterPage() {
  const [selected, setSelected] = useState<RegType>(null);

  return (
    <div className="mx-auto max-w-2xl space-y-8">
      <div className="space-y-2 text-center">
        <h1 className="text-3xl font-semibold text-navy">Join Imparency</h1>
        <p className="text-lg text-muted">Choose how you want to participate</p>
      </div>

      <div className="grid gap-6 md:grid-cols-2">
        {/* NGO Registration Card */}
        <div
          onClick={() => setSelected("ngo")}
          className={`cursor-pointer rounded-sm border-2 p-6 transition-all ${
            selected === "ngo"
              ? "border-navy bg-navy/5"
              : "border-line hover:border-navy hover:bg-navy/2"
          }`}
        >
          <div className="space-y-3">
            <h2 className="text-xl font-semibold text-navy">I run an NGO</h2>
            <p className="text-sm text-muted">
              Publish projects, receive donations, and build a verified profile that donors can trust.
            </p>
            <ul className="space-y-2 text-sm text-muted">
              <li>✓ Get verified by reviewers</li>
              <li>✓ Publish projects for donations</li>
              <li>✓ Respond to CSR opportunities</li>
              <li>✓ Receive direct donations</li>
            </ul>
            {selected === "ngo" && (
              <Link
                href="/register/ngo"
                className="mt-4 block rounded-sm bg-teal px-4 py-2 text-center font-display font-medium text-paper hover:opacity-90"
              >
                Continue as NGO
              </Link>
            )}
          </div>
        </div>

        {/* Donor / CSR Registration Card */}
        <div
          onClick={() => setSelected("donor")}
          className={`cursor-pointer rounded-sm border-2 p-6 transition-all ${
            selected === "donor"
              ? "border-navy bg-navy/5"
              : "border-line hover:border-navy hover:bg-navy/2"
          }`}
        >
          <div className="space-y-3">
            <h2 className="text-xl font-semibold text-navy">I give or manage giving</h2>
            <p className="text-sm text-muted">
              Keep track of your donations, create CSR opportunities, or give to verified NGOs.
            </p>
            <ul className="space-y-2 text-sm text-muted">
              <li>✓ Browse verified NGOs</li>
              <li>✓ Donate to projects</li>
              <li>✓ Create CSR opportunities</li>
              <li>✓ Track your giving history</li>
            </ul>
            {selected === "donor" && (
              <Link
                href="/register/donor"
                className="mt-4 block rounded-sm bg-teal px-4 py-2 text-center font-display font-medium text-paper hover:opacity-90"
              >
                Continue as Donor/CSR
              </Link>
            )}
          </div>
        </div>
      </div>

      {/* Already have account */}
      <div className="space-y-2 border-t-2 border-line pt-6 text-center">
        <p className="text-sm text-muted">Already have an account?</p>
        <Link href="/login" className="font-medium text-teal hover:underline">
          Sign in instead
        </Link>
      </div>
    </div>
  );
}
