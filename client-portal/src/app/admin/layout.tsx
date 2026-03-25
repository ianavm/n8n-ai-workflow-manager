import { AdminNav } from "@/components/admin/AdminNav";

export default function AdminLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <>
      <AdminNav />
      <main className="admin-content pt-14 lg:pt-0 min-h-screen overflow-x-hidden dot-matrix-bg">
        <div className="p-4 lg:p-8">{children}</div>
      </main>
    </>
  );
}
