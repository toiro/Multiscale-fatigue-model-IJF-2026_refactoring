# Resource Run Configs

This directory contains the normal calculation configs for the supported
resource condition directories. Config filenames match the condition directory
names, such as `N50R_CS_T50.json`. These configs follow the original
paper-script defaults:

- `sigma_nom`: `[150, 160, 170, 180, 190]`
- `iteration_count`: `4`
- `n_symm`: `4`
- no `random_seed`
- no `max_active_elements`

Lightweight seed-fixed configs for development verification live under
`verification/configs/conditions/` instead.
