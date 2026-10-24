# Stability notes | 稳定性说明

The stability framework that used to live in this file (decision framework, role registry,
rollback mechanism, batch safety limits and CI checks) has moved to
[docs/CONVENTIONS.md](../docs/CONVENTIONS.md). Role-specific verification and rollback steps are
documented in each role's `README.md`; the generic rollback tooling is described in
[roles/lifecycle/README.md](lifecycle/README.md).

原先记录在此文件中的稳定性框架（判别框架、角色清单、回滚机制、批量安全限制与 CI 检查）已迁移到
[docs/CONVENTIONS.md](../docs/CONVENTIONS.md)。各角色的验证与回滚步骤见各自的 `README.md`，
通用回滚工具见 [roles/lifecycle/README.md](lifecycle/README.md)。
