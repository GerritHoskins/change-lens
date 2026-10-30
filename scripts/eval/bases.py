"""Base briefs for constructed pairs (docs/07-eval-dataset.md §3).

Written for the purpose; no client data. Each item renders `tpl` with its value in
place of `{v}`. `para` is a meaning-preserving rewording, `alts` are changed values,
`vague` is an ambiguous replacement and `flip` is a modal or qualifier swap
(the words must appear in `tpl` but not in the value). People are anonymised
consistently as Contact A, Contact B, ...

Every paraphrase must keep the actor, the required action and its binding force
(07 §4). A person signs off each one before the set is used (07 §3); the sign-off
is recorded in docs/06-decision-log.md.
"""

BASES = [
    {
        "id": "B-001",
        "title": "Website redesign brief: Harbour Bakery",
        "sections": [
            {"name": "Deliverables", "items": [
                {"id": "pages", "cat": "quantity", "v": "8",
                 "tpl": "Design {v} page templates for the new website.",
                 "para": "The new website needs {v} page templates designed.",
                 "alts": ["6", "10"]},
                {"id": "format", "cat": "deliverable", "v": "SVG",
                 "tpl": "All icons must be delivered as {v} files.",
                 "para": "Every icon must be handed over as {v} files.",
                 "alts": ["PNG", "WebP"], "flip": ["must", "should"]},
                {"id": "tone", "cat": "deliverable", "v": "warm and playful",
                 "tpl": "The visual style of the designs is {v}.",
                 "para": "The designs have a {v} visual style.",
                 "alts": ["clean and corporate", "calm and minimal"]},
            ]},
            {"name": "Schedule", "items": [
                {"id": "review", "cat": "date_deadline", "v": "14 March 2027",
                 "tpl": "First design review on {v}.",
                 "para": "The first review of the designs takes place on {v}.",
                 "alts": ["21 March 2027", "7 March 2027"], "vague": "early next month"},
                {"id": "final", "cat": "date_deadline", "v": "30 April 2027",
                 "tpl": "Final files are due on {v}.",
                 "para": "The final files must reach us by {v}.",
                 "alts": ["29 April 2027", "15 May 2027"], "vague": "shortly after launch"},
            ]},
            {"name": "Budget", "items": [
                {"id": "budget", "cat": "other_material", "v": "EUR 18,000",
                 "tpl": "The total budget is {v}, including VAT.",
                 "para": "Including VAT, the budget comes to {v} in total.",
                 "alts": ["EUR 16,500", "EUR 20,000"], "flip": ["including", "excluding"]},
            ]},
            {"name": "Team and approvals", "items": [
                {"id": "copy", "cat": "responsibility_owner", "v": "Contact A",
                 "tpl": "Website copy is written by {v}.",
                 "para": "{v} writes the copy for the website.",
                 "alts": ["Contact B"], "vague": "someone from the team"},
                {"id": "approval", "cat": "approval", "v": "the client signs it off in writing",
                 "tpl": "Each milestone is complete when {v}.",
                 "para": "A milestone counts as complete once {v}.",
                 "alts": ["the client has reviewed it"]},
            ]},
        ],
    },
    {
        "id": "B-002",
        "title": "Brochure brief: Open Day at a regional university",
        "sections": [
            {"name": "Scope", "items": [
                {"id": "pages", "cat": "quantity", "v": "24",
                 "tpl": "Lay out a printed brochure of {v} pages.",
                 "para": "The printed brochure runs to {v} pages and needs laying out.",
                 "alts": ["20", "32"]},
                {"id": "print", "cat": "deliverable", "v": "print-ready PDF/X-4",
                 "tpl": "Artwork must be supplied as {v}.",
                 "para": "The artwork must come as {v}.",
                 "alts": ["editable InDesign files", "PDF for screen"],
                 "flip": ["must", "may"]},
                {"id": "photos", "cat": "quantity", "v": "15",
                 "tpl": "Retouch {v} campus photographs.",
                 "para": "{v} photographs of the campus need retouching.",
                 "alts": ["10", "25"]},
            ]},
            {"name": "Dates", "items": [
                {"id": "draft", "cat": "date_deadline", "v": "2 February 2027",
                 "tpl": "The first draft is due on {v}.",
                 "para": "The first draft must be delivered on {v}.",
                 "alts": ["3 February 2027", "26 January 2027"], "vague": "before the next board meeting"},
                {"id": "print_date", "cat": "date_deadline", "v": "1 March 2027",
                 "tpl": "Files go to the printer on {v}.",
                 "para": "On {v} the files are sent to the printer.",
                 "alts": ["22 February 2027", "8 March 2027"], "vague": "in good time for the event"},
            ]},
            {"name": "Fees", "items": [
                {"id": "fee", "cat": "other_material", "v": "GBP 6,400",
                 "tpl": "The fixed fee is {v}, excluding VAT.",
                 "para": "Excluding VAT, the fee is fixed at {v}.",
                 "alts": ["GBP 5,900", "GBP 7,200"], "flip": ["excluding", "including"]},
            ]},
            {"name": "Roles", "items": [
                {"id": "photo_owner", "cat": "responsibility_owner", "v": "Contact C",
                 "tpl": "Photography is organised by {v}.",
                 "para": "{v} organises the photography.",
                 "alts": ["Contact D"], "vague": "someone in marketing"},
                {"id": "signoff", "cat": "approval", "v": "the Head of Marketing approves the proof",
                 "tpl": "Printing starts only after {v}.",
                 "para": "Printing begins only after {v}.",
                 "alts": ["the proof has been circulated"], "flip": ["only after", "after"]},
            ]},
        ],
    },
    {
        "id": "B-003",
        "title": "Video campaign brief: river clean-up charity",
        "sections": [
            {"name": "Outputs", "items": [
                {"id": "videos", "cat": "quantity", "v": "3",
                 "tpl": "Produce {v} short videos for social media.",
                 "para": "{v} short social media videos are to be produced.",
                 "alts": ["2", "5"]},
                {"id": "res", "cat": "deliverable", "v": "1080p",
                 "tpl": "Each video must be exported in {v}.",
                 "para": "Every video must be exported in {v}.",
                 "alts": ["4K", "720p"], "flip": ["must", "should"]},
                {"id": "length", "cat": "deliverable", "v": "30 seconds",
                 "tpl": "No video may be longer than {v}.",
                 "para": "The maximum length of any video is {v}.",
                 "alts": ["45 seconds", "20 seconds"], "flip": ["may", "should"]},
            ]},
            {"name": "Timeline", "items": [
                {"id": "shoot", "cat": "date_deadline", "v": "10 June 2027",
                 "tpl": "Filming takes place on {v}.",
                 "para": "The shoot is on {v}.",
                 "alts": ["17 June 2027", "9 June 2027"], "vague": "a weekend in summer"},
                {"id": "launch", "cat": "date_deadline", "v": "1 July 2027",
                 "tpl": "The campaign launches on {v}.",
                 "para": "Launch of the campaign is set for {v}.",
                 "alts": ["8 July 2027", "30 June 2027"], "vague": "when the weather improves"},
            ]},
            {"name": "Budget", "items": [
                {"id": "budget", "cat": "other_material", "v": "EUR 9,500",
                 "tpl": "The production budget is capped at {v}.",
                 "para": "Production costs are capped at {v}.",
                 "alts": ["EUR 8,000", "EUR 11,000"], "flip": ["capped", "estimated"]},
            ]},
            {"name": "Responsibilities", "items": [
                {"id": "music", "cat": "responsibility_owner", "v": "Contact E",
                 "tpl": "Music licensing is handled by {v}.",
                 "para": "{v} takes care of music licensing.",
                 "alts": ["Contact F"], "vague": "whoever is available"},
                {"id": "approval", "cat": "approval", "v": "the trustees sign off the final cut",
                 "tpl": "Videos are published after {v}.",
                 "para": "Publication follows once {v}.",
                 "alts": ["the trustees have seen the final cut"]},
            ]},
        ],
    },
]
