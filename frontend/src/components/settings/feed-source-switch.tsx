import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { api, errorMessage } from "@/api";
import { Switch } from "@/components/ui/switch";

export function FeedSourceSwitch({ sourceKey, name, enabled }: { sourceKey: string; name: string; enabled: boolean }) {
  const qc = useQueryClient();
  const mutation = useMutation({
    mutationKey: ["source-toggle", sourceKey],
    mutationFn: (value: boolean) => api.updateSource(sourceKey, { enabled: value }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["sources"] });
      qc.invalidateQueries({ queryKey: ["feeds"] });
    },
    onError: (e) => toast.error(errorMessage(e)),
  });
  return <Switch aria-label={`Enable ${name}`} checked={enabled} disabled={mutation.isPending} onCheckedChange={(value) => mutation.mutate(value)} />;
}