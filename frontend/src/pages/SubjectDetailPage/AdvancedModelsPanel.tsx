import { Link } from "react-router-dom";
import { ChevronDown, FlaskConical, Sparkles } from "lucide-react";
import { Badge, statusTone } from "@/components/Badge";
import { Button } from "@/components/Button";
import { SubjectDetail } from "@/api/client";

type Props = {
  subject: SubjectDetail;
  expanded: boolean;
  onToggleExpanded: () => void;
  trainingAlt: "IF" | "LSTM" | null;
  onTrainAlternative: (algorithm: "IF" | "LSTM") => void;
  activatingModelId: number | null;
  onActivateModel: (modelId: number) => void;
};

export function AdvancedModelsPanel({
  subject,
  expanded,
  onToggleExpanded,
  trainingAlt,
  onTrainAlternative,
  activatingModelId,
  onActivateModel,
}: Props) {
  return (
    <div className="mt-5 border-t border-border pt-4">
      <button
        onClick={onToggleExpanded}
        className="flex w-full items-center justify-between text-left text-xs font-semibold uppercase tracking-wider text-muted hover:text-text"
      >
        Advanced
        <ChevronDown className={`h-3.5 w-3.5 transition-transform duration-200 ${expanded ? "rotate-180" : ""}`} />
      </button>
      <div className={`grid transition-[grid-template-rows] duration-200 ease-out ${expanded ? "grid-rows-[1fr]" : "grid-rows-[0fr]"}`}>
        <div className="overflow-hidden">
          <div className="mt-4 space-y-4">
            <div>
              <p className="text-sm font-medium text-text">Alternative algorithms</p>
              <p className="mt-0.5 text-xs text-muted">
                Train a different algorithm for comparison. This is useful for research and doesn&apos;t replace your active model.
              </p>
              <div className="mt-3 flex gap-2">
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => onTrainAlternative("IF")}
                  loading={trainingAlt === "IF"}
                  disabled={subject.datasets.length === 0 || trainingAlt !== null}
                  icon={<Sparkles className="h-3.5 w-3.5" />}
                >
                  Train Isolation Forest
                </Button>
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => onTrainAlternative("LSTM")}
                  loading={trainingAlt === "LSTM"}
                  disabled={subject.datasets.length === 0 || trainingAlt !== null}
                  icon={<Sparkles className="h-3.5 w-3.5" />}
                >
                  Train LSTM Autoencoder
                </Button>
              </div>
            </div>

            {subject.models.length > 0 && (
              <div>
                <p className="text-sm font-medium text-text">Models trained on this subject ({subject.models.length})</p>
                <ul className="mt-2 divide-y divide-border">
                  {subject.models.map((m) => (
                    <li key={m.id} className="flex items-center justify-between gap-3 py-2 text-xs">
                      <div className="flex items-center gap-2">
                        <span className={`h-1.5 w-1.5 rounded-full ${m.is_active ? "bg-success" : "bg-border"}`} />
                        <span className="text-text">Model #{m.id}</span>
                        <Badge tone="accent">{m.algorithm}</Badge>
                        <Badge tone={statusTone(m.status)}>{m.status}</Badge>
                      </div>
                      <div className="flex items-center gap-3">
                        <span className="font-mono text-muted">{m.threshold ? `ε=${m.threshold.epsilon.toFixed(4)}` : "-"}</span>
                        {m.evaluation && (
                          <>
                            {m.evaluation.f1 !== null && (
                              <span className="font-mono text-muted" title="F1 on held-out test set">
                                F1={m.evaluation.f1.toFixed(3)}
                              </span>
                            )}
                            <Link to={`/models/${m.id}/diagnostics`} className="text-muted hover:text-accent" title="Open diagnostics">
                              <FlaskConical className="h-3.5 w-3.5" />
                            </Link>
                          </>
                        )}
                        {!m.is_active && m.status === "ready" && (
                          <Button variant="ghost" size="sm" onClick={() => onActivateModel(m.id)} loading={activatingModelId === m.id}>
                            Make active
                          </Button>
                        )}
                      </div>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
