import { Suspense } from 'react';
import { Skeleton } from '@/components/ui/skeleton';

// 1. Define the Data Fetching Logic (Server Side)
async function getProjectData(id: string) {
  const res = await fetch(`https://api.example.com/projects/${id}`, {
    next: { revalidate: 3600 } // Cache for 1 hour
  });
  
  if (!res.ok) throw new Error('Failed to fetch data');
  return res.json();
}

// 2. Main Server Component (Async)
export default async function ProjectPage({ params }: { params: { id: string } }) {
  const { id } = params;

  return (
    <div className="container mx-auto py-8">
      <h1 className="text-3xl font-bold mb-6">Project Details</h1>
      
      {/* 3. Use Suspense for Granular Loading */}
      <Suspense fallback={<ProjectSkeleton />}>
        <ProjectDetails id={id} />
      </Suspense>
    </div>
  );
}

// 4. Sub-component for Data Rendering
async function ProjectDetails({ id }: { id: string }) {
  const data = await getProjectData(id);
  
  return (
    <div className="bg-card p-6 rounded-lg shadow">
      <h2 className="text-xl font-semibold">{data.name}</h2>
      <p className="mt-2 text-muted-foreground">{data.description}</p>
      {/* Client Component leaf */}
      <ProjectActions id={id} />
    </div>
  );
}

function ProjectSkeleton() {
  return <Skeleton className="h-[200px] w-full" />;
}

// Dummy Client Component import placeholder
function ProjectActions({ id }: { id: string }) {
    return <div className="mt-4">Actions for {id}</div>;
}
