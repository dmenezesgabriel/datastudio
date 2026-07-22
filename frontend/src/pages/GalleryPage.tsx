import { ArtifactGallery } from "../components/ArtifactGallery";
import { useArtifacts } from "../hooks/useArtifacts";
import { useDocumentTitle } from "../hooks/useDocumentTitle";

// The gallery of saved dashboards, addressed by URL. It owns the artifact list rather than
// the app shell: mounting on navigation re-fetches it, so a dashboard saved by a chat turn
// is already there when the user arrives.
export function GalleryPage() {
  const { artifacts, deleteArtifact } = useArtifacts();
  useDocumentTitle("Saved dashboards");
  return (
    <main className="main">
      <ArtifactGallery artifacts={artifacts} onDelete={(id) => void deleteArtifact(id)} />
    </main>
  );
}
