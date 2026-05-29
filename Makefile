.PHONY: public-release-check public-audit public-audit-strict skill-audit capability artifact-scan example-preflight demo-campaign-dry-run demo-campaign-smoke demo-campaign-public-mining demo-explore demo-explore-clean path-scan unit py-compile clean-generated forbidden-file-scan heavy-file-scan ignored-artifact-check

public-release-check:
	$(MAKE) clean-generated
	$(MAKE) public-audit
	$(MAKE) demo-campaign-dry-run
	$(MAKE) unit
	$(MAKE) py-compile
	$(MAKE) public-audit-strict

public-audit: skill-audit capability example-preflight path-scan

public-audit-strict:
	$(MAKE) clean-generated
	$(MAKE) artifact-scan
	$(MAKE) path-scan
	$(MAKE) forbidden-file-scan
	$(MAKE) heavy-file-scan
	$(MAKE) ignored-artifact-check

skill-audit:
	PYTHONDONTWRITEBYTECODE=1 python3 -B skills/biosymphony/scripts/biosymphony_public_skill_audit.py --skill-root skills/biosymphony

capability:
	PYTHONDONTWRITEBYTECODE=1 python3 -B skills/biosymphony/scripts/capability_probe.py --json --no-fail

artifact-scan:
	PYTHONDONTWRITEBYTECODE=1 python3 -B skills/biosymphony/scripts/genecluster_preflight.py \
	  --repo-root . \
	  --scan-local-artifacts

example-preflight:
	PYTHONDONTWRITEBYTECODE=1 python3 -B skills/biosymphony/scripts/genecluster_preflight.py \
	  --campaign skills/biosymphony/examples/genecluster-coptis-bia-public-v0/campaign-manifest.json \
	  --project-goals skills/biosymphony/examples/genecluster-coptis-bia-public-v0/project-goals.yaml \
	  --pathway-steps skills/biosymphony/examples/genecluster-coptis-bia-public-v0/pathway-steps.tsv \
	  --data-ledger skills/biosymphony/examples/genecluster-coptis-bia-public-v0/data-ledger.tsv \
	  --query-ledger skills/biosymphony/examples/genecluster-coptis-bia-public-v0/query-ledger.tsv \
	  --resource-ledger skills/biosymphony/examples/genecluster-coptis-bia-public-v0/resource-ledger.tsv \
	  --database-ledger skills/biosymphony/examples/genecluster-coptis-bia-public-v0/database-ledger.tsv \
	  --cache-ledger skills/biosymphony/examples/genecluster-coptis-bia-public-v0/cache-ledger.tsv

demo-campaign-dry-run:
	bash tools/genecluster_demo_harness.sh

demo-campaign-smoke:
	BIOSYMPHONY_DEMO_SCOPE=smoke bash tools/genecluster_demo_harness.sh

demo-campaign-public-mining:
	BIOSYMPHONY_DEMO_SCOPE=full_public_mining bash tools/genecluster_demo_harness.sh

demo-explore:
	@rm -rf .demo-output
	@mkdir -p .demo-output
	BIOSYMPHONY_DEMO_OUT=.demo-output bash tools/genecluster_demo_harness.sh
	@printf '\nOpen these to explore the output:\n'
	@printf '  .demo-output/README.md                       (orientation)\n'
	@printf '  .demo-output/review/index.html               (static review surface)\n'
	@printf '  .demo-output/route-scout/route_decision.json (route card and claim ceiling)\n'
	@printf '  .demo-output/dossier/dossier-manifest.json   (summary-only dossier manifest)\n'
	@printf '  .demo-output/issues/                         (candidate-search issue drafts)\n'
	@printf '\nWhen done: make demo-explore-clean\n'

demo-explore-clean:
	@rm -rf .demo-output

path-scan:
	! rg -uu --hidden -n '/Users/[A-Za-z0-9._-]+|rp_[A-Za-z0-9_]{10,}|ghp_[A-Za-z0-9]{20,}|gho_[A-Za-z0-9]{20,}|sk-[A-Za-z0-9]{20,}|x-access-token|[A-Za-z0-9._%+-]+@(gmail|icloud|me|hotmail|outlook|yahoo)\\.com' . --glob '!.git/**' --glob '!Makefile' --glob '!.gitignore' --glob '!docs/diagrams/*.svg' --glob '!docs/diagrams/**/*.svg'

unit:
	PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest skills/biosymphony/tests/test_genecluster.py

py-compile:
	find skills/biosymphony/scripts skills/biosymphony/remote pipeline tools -name '*.py' -print0 | PYTHONPYCACHEPREFIX="$${TMPDIR:-/tmp}/biosymphony-genecluster-pycache" xargs -0 python3 -m py_compile

clean-generated:
	find . \( -path './.git' -o -path './.git/*' \) -prune -o -type d \( -name '__pycache__' -o -name '.pytest_cache' \) -prune -exec rm -rf {} +
	@rm -rf .demo-output

forbidden-file-scan:
	! find . \( -path './.git' -o -path './.git/*' \) -prune -o \( -type d \( -name '.runtime' -o -name 'logs' -o -name '__pycache__' -o -name '.pytest_cache' -o -name '.runpod-dispatch' -o -name '.lambda-dispatch' -o -name '.vastai-dispatch' -o -name '.aws-dispatch' -o -name '.gcp-dispatch' \) -o -type f \( -name '*.env' -o -name '*create-response.json' -o -name '*-create-response.json' -o -name '*-payload.json' -o -name '*-launch.json' -o -name '*-launch-response.json' -o -name '*-http-code' -o -name '*-instance-id' -o -name '*pod-id*' -o -name '*.log' -o -name '*.fastq*' -o -name '*.sra' -o -name '*.bam' -o -name '*.cram' -o -name '*.dmnd' -o -name '*.sqlite' -o -name '*.pt' -o -name '*.pth' \) \) -print | rg .

heavy-file-scan:
	! find . -type f -size +5M -not -path './.git/*' -print | rg .

ignored-artifact-check:
	git check-ignore -q .runtime/provider-dispatch/runpod/example-payload.json
	git check-ignore -q .runtime/provider-dispatch/runpod/example-pod-id
	git check-ignore -q .runtime/provider-dispatch/lambda/example-launch.json
	git check-ignore -q .runpod-dispatch/example-create-response.json
