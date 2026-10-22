'use client';

import { OrgDirectory } from '@/components/admin/OrgDirectory';

export default function AdminDonorsPage() {
  return (
    <OrgDirectory
      orgType="CSR"
      title="CSR / funding organisations"
      blurb="Every CSR and corporate funding organisation on the platform. Individual donors (people giving as themselves, not through an organization) are on a separate page."
      countLabel="Campaigns"
    />
  );
}
