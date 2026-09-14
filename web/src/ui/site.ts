/**
 * The two addresses this site knows about itself, in one place: the footer, the
 * landing paragraph, the About page and the review route's "Report on GitHub"
 * link all point at the same repository, and a fork only has to change it here.
 *
 * `SITE_URL` is the published address, not `import.meta.env.BASE_URL`: it is
 * only ever used to build a link that leaves the page (an issue body), where a
 * `localhost:5173` URL would be useless to whoever reads it.
 */
export const REPO_URL = 'https://github.com/Deradon/wow-forever-talent-calc'
export const SITE_URL = 'https://deradon.github.io/wow-forever-talent-calc/'
export const ISSUES_URL = `${REPO_URL}/issues`
export const DISCUSSIONS_URL = `${REPO_URL}/discussions`
