# 0036: License the repository under AGPL-3.0

- Date: 2026-10-26
- Status: proposed

## Context

The repository is public but had no license, so by default all rights were reserved: GitHub's Terms of Service only let others view and fork it on GitHub ([§D.5](https://docs.github.com/en/site-policy/github-terms/github-terms-of-service#5-license-grant-to-other-users), read 2026-10-26). Since 2026-10-20, external contributors have opened pull requests against the audit issues, and one (#220) was merged. GitHub's "inbound = outbound" rule ([§D.6](https://docs.github.com/en/site-policy/github-terms/github-terms-of-service#6-contributions-under-repository-license), read 2026-10-26) only applies to "a repository containing notice of a license", so without one, contributors keep the copyright of their code and grant no explicit license to the project.

Alternatives considered:

- **No license, no external contributions.** Keeps every right, but the team wants to accept contributions.
- **MIT or Apache-2.0.** Permissive and frictionless for contributors, but anyone could run a modified copy of the product as a closed SaaS.
- **A contributor license agreement (CLA) with no open license.** Gives the project rights over contributions, but adds friction for every contributor and still leaves the code all-rights-reserved for readers.

## Decision

License the whole repository under the [GNU Affero General Public License v3.0](../../LICENSE) (`AGPL-3.0-only`), with the unmodified text from [gnu.org](https://www.gnu.org/licenses/agpl-3.0.txt) in `LICENSE` at the repository root.

## Consequences

- From now on, contributions are licensed to the project under AGPL-3.0 by GitHub's §D.6, with no CLA.
- Anyone who runs a modified version as a network service must offer its source to its users (AGPL §13). This protects the product from closed clones.
- Contributors keep the copyright of their code, so the project cannot later relicense or sell a commercial license over third-party code without their consent or a CLA. Code already merged belongs to its authors: the team's members agree to the license by approving this ADR.
- Vendored files under `.claude/` keep their own licenses (MIT, Apache-2.0), listed in [THIRD_PARTY_NOTICES.md](../../.claude/THIRD_PARTY_NOTICES.md); both are compatible with AGPL-3.0.
- New dependencies must have a license compatible with AGPL-3.0, which rules out proprietary or "no commercial use" licenses.
