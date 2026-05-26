# greytHR Support — Questions Before 300-Employee Onboarding

> **Context to share at the start of any call/email**:
>
> *Globex Digital Solutions Pvt Ltd is a contract-staffing company. We deploy employees to client sites via Principal Employers — typical chain: Globex (Contractor) → Kyndryl Solutions (Principal Employer) → Dr Reddy's Laboratories Generics Unit, Bachupally (actual workplace). We currently have ~340 active employees on greytHR (Establishment Code: APKKP1666408000, ESIC Code: 52000653990001099) deployed across Hyderabad, Baddi (HP), Pydibhimavaram (AP), and Vizag (AP) sub-units (PU2, FTO 9, FTO 11). We have a 300-employee onboarding deal closing in the next 60 days. We want to verify greytHR can fully handle our statutory compliance reporting (Contract Labour Act forms per location + central PF/ESIC/Maternity/IW-1) at this scale before we commit. Please find our specific questions below — answers in writing (email reply) preferred for our records.*

---

## A. Plan + Module activation

1. We're currently on **[your current plan name]** with ~340 employees. After the 60-day push we'll be at ~640. Which plan tier supports our needs (Contractor Management + multi-location compliance + state-specific CLRA forms)?

2. Is the **Contractor Management Module** included in our current plan, or does it need to be activated separately?

3. What's the per-employee monthly cost on our current plan vs the recommended tier?

4. How quickly can the upgrade be activated and the Contractor Module enabled? (We need to start configuring within a week.)

5. Any one-time setup / implementation / training fees on top of the per-employee cost?

---

## B. Contractor / multi-Principal-Employer setup

6. We're a Contractor with this 3-tier hierarchy: **Globex (us) → Principal Employer (Kyndryl) → Actual Workplace (Dr Reddy's Generics Unit)**. Can your platform model this 3-tier relationship?

7. We have multiple Principal Employers across the same workforce (Kyndryl, Dr Reddy's, and more coming with the 300). Does the platform support employees deployed to different Principal Employers under different sub-contracts?

8. Can the same employee be transferred between Principal Employers / worksites mid-contract, with full compliance history preserved?

9. How does the platform handle a Principal Employer chain where the contracting party (Kyndryl) is different from the workplace (Dr Reddy's)? On Form XIII we currently print BOTH (Kyndryl as "establishment in/under which contract is carried on" + Dr Reddy's as "Principal Employer"). Does greytHR's Form XIII auto-populate both fields correctly?

---

## C. Worksite / location setup

10. We have ~6 distinct worksites today: Hyderabad (Dr Reddy's), Baddi (HP), Pydibhimavaram + Vizag sub-units (PU2, FTO 9, FTO 11). Can we configure each as a separate Worksite/Branch in greytHR?

11. For each worksite, can we set state-specific attributes (state PF region, state ESIC region, state PT, state-specific CLRA Rules variant)?

12. Can compliance reports be generated **per worksite per month** in a single batch operation (vs. running per worksite manually)?

---

## D. Contract Labour Act (CLRA) forms

We currently generate ~9 forms per location per month under the **Contract Labour (Regulation & Abolition) Act 1970** + state Rules. Specifically:

| Form | Title |
|---|---|
| **Form XIII** | Register of Workmen Employed by Contractor |
| **Form XIV** | Employment Card (per-employee) |
| **Form XVI** | Muster Roll |
| **Form XVII** | Wage Register |
| **Form XIX** | Wage Slips |
| **Form XX** | Register of Damages & Deductions + Register of Leave (two separate registers, same form number) |
| **Form XXI** | Register of Fines |
| **Form XXII** | Register of Advances |
| **Form XXIII / XXIIII** | Register of Overtime |

Questions:

13. Does the Contractor Management Module **auto-generate all 9 of these forms** per worksite per month, OR are some manual?

14. **State variants** — we need:
    - **Himachal Pradesh** rules for Baddi (current forms are labeled "HP", e.g., "Muster roll XVI HP_Feb 2026.pdf")
    - **Telangana** rules for Hyderabad
    - **Andhra Pradesh** rules for Pydi/Vizag
    
    Does greytHR have state-specific layouts for HP, Telangana, and AP CLRA Rules? Or are forms generated to a central format that may need state-level adaptation?

15. If a state variant isn't directly supported, can we **upload our own custom template** (Word/HTML) that greytHR fills with employee data?

16. Form XIV (Employment Card) — does it auto-generate on employee onboarding, or generated on-demand?

17. Forms XX/XXI/XXII/XXIII (Damages/Leave/Fines/Advances/Overtime registers) — do these auto-populate from your built-in leave, payroll, advances, and attendance modules? Or do we have to enter the data separately?

18. Where in the form (or the master data) is the **"On account of [Principal Employer]"** label set? On Form XIII we print "Globex Digital Solutions Pvt Ltd... On account of Kyndryl". We need this to switch per Principal Employer per location.

---

## E. Central statutory reports (already mostly working — confirm)

19. Confirm the following are auto-generated by greytHR (we believe yes, just confirming for our 60-day plan):
    - **PF Combined Challan** + **ECR `.txt` file** (for EPFO portal upload)
    - **ESIC ECR + Challan** (for ESIC portal upload)
    - **IW-1 International Workers Return** (currently NIL for us)
    - **Form A (Maternity Benefit Act 1961)** — per-female-employee monthly muster roll
    - **Form 24Q TDS** (quarterly)
    - **Form 16** (annual)
    - **Professional Tax** returns for Telangana, AP, HP
    - **Labour Welfare Fund** (LWF) for relevant states

20. For PF/ESIC, does greytHR **auto-upload** to the EPFO/ESIC portals, or only generate files for manual upload, or both?

21. We have not yet uploaded an IW-1 return for any month — when we get an international worker (or someone going abroad on assignment), what's the workflow?

---

## F. Custom letters / declarations

22. We send a **Salary Transfer Declaration letter** to each Principal Employer every month — cover letter on Globex letterhead + table of employees deployed there + their NET PAY + bank details. Can greytHR's **Letter Templates / Compliance Letters module**:

    a. Let us upload our existing Word template with placeholders (`{{employee_name}}`, `{{net_pay}}`, `{{bank}}`, `{{ifsc}}`, `{{acc_no}}`)?
    
    b. Filter the employee table by Principal Employer (so the Kyndryl letter only shows Kyndryl-deployed employees)?
    
    c. Generate one letter per Principal Employer per month, on demand?
    
    d. Email the letter directly to the Principal Employer's contact, OR save as PDF for manual emailing?

23. Are there limits on the number of custom letter templates we can configure? We may have 5-10 different templates (one per major Principal Employer + a few internal letters).

---

## G. Bulk onboarding (300 employees in 60 days)

24. What's the **fastest** way to onboard 300 employees? Options to compare:
    - Excel bulk import
    - API-based import
    - Manual one-by-one
    - Onboarding workflow with self-service candidate form

25. For Excel bulk import, do you provide a template? What fields are **mandatory** vs **optional**? Can we onboard with minimal data (name + employee_number + DOJ) and enrich later (PF/ESIC numbers added once issued)?

26. The 300 will be assigned to **several different Principal Employers + worksites**. Can the bulk import assign these per row?

27. **PF/ESIC account creation** — does greytHR auto-create PF UAN + ESIC IP numbers for new hires, or do we file Form 11 manually for each?

28. Offer letter generation — does greytHR support **bulk offer letter generation** (300 letters from one Excel + one template) or only one-at-a-time?

29. Onboarding tasks (document collection, ID issuance, induction) — can these be defined as a workflow that auto-triggers on hire?

---

## H. Existing employee data migration

30. We've already cleaned up our 340-employee database in greytHR (employee numbers aligned to GDS####, mapping corrections done). The Contractor Module activation — will it **re-import** any data or **modify existing employee records destructively**?

31. We currently use a separate Frappe HR app for custom-branded letters. We plan to retire Frappe HR going forward. Is there a way to import any historical letter PDFs (offer letters, etc.) into greytHR's Documents module as historical attachments?

---

## I. Compliance audit + client expectations

32. Our pharma clients (Dr Reddy's, etc.) periodically audit our Contract Labour compliance at their sites. Can greytHR produce an **audit-ready compliance binder** (all forms for a given period for a given Principal Employer) on demand?

33. In the event of a **Labour Department inspection** at a client site, can the platform produce historical compliance documents (Form XIII for the last 12 months, all wage registers, etc.) in a single export?

34. Do you have a **compliance certification document** confirming greytHR meets statutory requirements for CLRA Act + state Rules in HP, Telangana, and AP? Useful when client audit asks for our compliance toolchain.

---

## J. API / Integration

35. We've been using greytHR's API for one-way sync to a parallel Frappe HR app. After Contractor Module activation, are **new API endpoints** exposed for:
    - Listing Principal Employers
    - Listing Worksites
    - Per-worksite employee deployment data
    - CLRA forms metadata

36. We plan to gradually retire the Frappe HR bridge. **Bulk export** capabilities — can we extract employee master + payroll history + all generated letters into a single archive?

---

## K. Training, support, and timeline

37. Do you provide **training** for our HR team specifically on the Contractor Module + multi-Principal-Employer + multi-location workflows? Format (videos, live sessions, in-person)?

38. What's your **support SLA** for issues during our 60-day onboarding push (Mar–May 2026)? Can we get a **dedicated account manager** during this window?

39. If we hit a **gap** (e.g., a specific state form variant doesn't exist, or a custom template doesn't render correctly), what's the process? Roadmap request? Custom-dev quote? Workaround via Excel export + manual?

40. Recommended **implementation sequence**:
    - Week 1: Configure Worksites + Principal Employers + Letter Templates
    - Week 2: Pilot onboard 10 employees end-to-end
    - Week 3: Run a FULL monthly compliance cycle (all 7 central + 6 location form-sets) — validate every PDF against our current ones
    - Week 4: Fix gaps, run pilot again
    - Week 5-9: Bulk onboard the 300 in batches
    - Week 10: First full monthly compliance cycle at 640-employee scale
    
    Does this match your typical implementation timeline? Anything you'd change?

---

## L. Pricing summary (please confirm in writing)

41. For 640 active employees on the **recommended plan with Contractor Module enabled**, please confirm:
    - Monthly per-employee cost
    - Annual total cost (if billed annually)
    - One-time setup fees (if any)
    - Professional services / template setup fees (if any)
    - Cost of any state-specific template customisation (HP, Telangana, AP CLRA variants)
    - Cost of dedicated account manager (if separate)
    - Notice period to scale down (if onboardings don't materialize)

---

## Deliverables we'd like back from greytHR

When responding, please include:

1. **Plan recommendation** with explicit confirmation of which features are included
2. **Demo** of the Contractor Management Module (screen-share session — 30-60 min)
3. **Sample state-specific forms** if you support them (one HP + one AP + one Telangana CLRA form)
4. **Bulk-onboarding Excel template** with all fields documented
5. **Sample compliance audit binder** (any anonymised customer)
6. **Pricing quote** (per §L above)
7. **Named contact** for our 60-day push (dedicated account manager preferred)

---

## What we'd accept as "yes, this will work"

To commit to greytHR-only path for the 300-employee push, we need:

- ✅ All 9 CLRA forms per location auto-generated (Form XIII through XXIII)
- ✅ At minimum: configurable templates for HP / Telangana / AP variants (even if not pre-built, we can configure)
- ✅ Multi-Principal-Employer + multi-Worksite hierarchy works
- ✅ Bulk import of 300 employees in a single batch
- ✅ Custom letter templates (Salary Transfer Declaration) with per-Principal-Employer filtering
- ✅ Pricing within our budget at 640-employee scale
- ✅ Implementation feasible in 4-week pilot window

If any of these are NO, please be upfront — we'd rather know now than mid-onboarding.

---

**Compiled for**: Globex Digital Solutions Pvt Ltd
**Date**: 2026-05-26
**Contact**: HR / IT lead at hr@globexdigital.ai
