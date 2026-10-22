'use client';

import { OrgDirectory } from '@/components/admin/OrgDirectory';

export default function AdminNgosPage() {
  return (
    <OrgDirectory
      orgType="NGO"
      title="NGOs"
      blurb="Every registered NGO and where it stands. Filter by status to see who is still waiting on verification."
      countLabel="Projects"
    />
  );
}
