# Sidebar Simplification — Design (2026-07-17)

## Goal

Make the sidebar read as a numbered, plain-language flow so any user type
understands the upload order without training.

## Approved decisions

- Depth: plain-language labels + numbered flow. No wizard restructure, no
  logic changes.
- Dark green = `#1b5e20`, bold, applied via `st-key-*` container CSS (same
  pattern as the stepper buttons).

## New sidebar order

1. **Step 1 · App URL & Login Details** — Global_Project_Data expander moved
   to top (`st.container(key="gpd_section")`). Helper caption inside. Upload
   still requires an existing project; warning unchanged.
2. **Step 2 · Project & User Story** — Project selectbox (bold dark-green
   label via `key="project_select"` container). Story selectbox label hidden
   (`label_visibility="collapsed"`). Add-story expander renamed
   "➕ Add a new user story (.txt)".
3. **Step 3 · Test Data (optional · JSON / CSV / Excel)** — expander wrapped
   in `st.container(key="testdata_section")`, bold dark-green label.
4. Run control / More — unchanged.

## Non-goals

- No workspace.py changes, no pipeline behavior changes, no wizard gating.
