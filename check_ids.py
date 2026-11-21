html = open('src/ui/static/index.html', encoding='utf-8').read()
ids = [
    'sp-403','sp-error','sp-content','sp-skeleton-header','sp-skeleton-skills','sp-skeleton-assess',
    'sp-name-badge','sp-student-name','sp-grade','sp-data-status','sp-data-dot','sp-data-label',
    'sp-exam-count','sp-skill-ratio','sp-skill-list','sp-assess-content','sp-weak-block',
    'sp-weak-title','sp-weak-text','sp-rec-text','sp-cta-bar','sp-generate-btn','sp-back-btn',
    'sp-retry-btn','sp-error-title','sp-error-msg','screen-exam','screen-profile',
    'sp-header-left','sp-header-stats',
]
missing = [i for i in ids if f'id="{i}"' not in html]
if missing:
    print('MISSING IDs:', missing)
else:
    print(f'All {len(ids)} required IDs present in HTML')

js = open('src/ui/static/app.js', encoding='utf-8').read()
fns = ['parseHash','navigateToProfile','spLoadStudentData','spRenderProfile',
       'spShowSkeleton','spHideSkeleton','spShow403','buildAssessment','deriveDataStatus']
missing_js = [f for f in fns if f not in js]
if missing_js:
    print('MISSING JS functions:', missing_js)
else:
    print(f'All {len(fns)} JS functions present')
