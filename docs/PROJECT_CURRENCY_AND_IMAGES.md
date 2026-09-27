# Project currency corrections and images

## Currency

System Administrators can add a currency from the project editor and correct the shared symbol of the project's current base currency. A symbol edit affects every project and record using that currency. Reporting currency remains editable in the ordinary project form.

Once a project leaves setup, its base currency is changed through **Correct base currency**, with a reason and an explicit acknowledgement that recorded numeric amounts stay unchanged. The operation changes the project base currency, updates reporting currency if it matched the old base, and relabels project-scoped rows explicitly denominated in the old currency. Rows denominated in another currency are left alone. Implicit base-currency amounts, such as land purchase prices, keep their numbers and take the corrected base label. No exchange rate or conversion is applied.

The correction locks the project and commits row changes and audit events in one transaction. The currency column map in `app/modules/projects/currency_correction.py` is checked against the model metadata before a correction; a new currency-bearing table must be reviewed and mapped before corrections can proceed. The audit trail records the old and new currency identifiers, reason, actor, and affected-row counts. Review financial reports after a correction because their currency labels can change while values remain fixed.

An unused currency can be removed with a reason. Database foreign keys block removal while any project, country pack, or financial record references it. The audit event remains after removal.

## Images

Project writers can add JPEG, PNG or WebP images, up to 10 MB each, under Interior, Exterior, or 3D shots. Images are stored inside the database and served through project-scoped authenticated routes. Viewers with project access can see the gallery. Removing an image hides it from the gallery and file route while retaining its row and audit event. The migration refuses rollback once image history exists.
