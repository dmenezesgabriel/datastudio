import { useParams } from "react-router-dom";

import { ArtifactView } from "../components/ArtifactView";
import { NotFoundPage } from "./NotFoundPage";

// One saved dashboard, addressed by URL. `key` remounts the view (and its per-artifact
// state) when the id changes, which is what ArtifactView's "keyed upstream" note relies on.
// The view names the tab itself — it is the only holder of the dashboard's title.
export function ArtifactPage() {
  const { artifactId } = useParams<{ artifactId: string }>();
  if (!artifactId) return <NotFoundPage />;
  return <ArtifactView key={artifactId} artifactId={artifactId} />;
}
