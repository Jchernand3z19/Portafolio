(() => {
  function setupSite(){
    const toggle=document.getElementById('menu-toggle');
    const links=document.getElementById('nav-links');
    if(toggle&&links){
      toggle.addEventListener('click',()=>{
        const open=links.classList.toggle('is-open');
        toggle.setAttribute('aria-expanded',String(open));
      });
      links.querySelectorAll('a').forEach(a=>a.addEventListener('click',()=>{
        links.classList.remove('is-open');
        toggle.setAttribute('aria-expanded','false');
      }));
    }

    const items=[...document.querySelectorAll('.fade-in')];
    if('IntersectionObserver' in window){
      const obs=new IntersectionObserver(entries=>entries.forEach(e=>{
        if(e.isIntersecting){
          e.target.classList.add('is-visible');
          obs.unobserve(e.target);
        }
      }),{threshold:.12});
      items.forEach(x=>obs.observe(x));
    }else{
      items.forEach(x=>x.classList.add('is-visible'));
    }

    const sections=[...document.querySelectorAll('[data-section]')];
    const nav=[...document.querySelectorAll('.nav__link')];
    const progressDots=[...document.querySelectorAll('.scroll-progress__dot')];
    const setActiveSection=id=>{
      nav.forEach(a=>a.classList.toggle('is-active',a.getAttribute('href')==='#'+id));
      progressDots.forEach(dot=>dot.classList.toggle('is-active',dot.dataset.sectionDot===id));
    };
    if('IntersectionObserver' in window){
      const active=new IntersectionObserver(entries=>{
        const visible=entries.filter(e=>e.isIntersecting).sort((a,b)=>b.intersectionRatio-a.intersectionRatio);
        if(!visible.length)return;
        const id=visible[0].target.id;
        setActiveSection(id);
      },{rootMargin:'-30% 0px -55% 0px',threshold:[.05,.25,.5]});
      sections.forEach(s=>active.observe(s));
    }


const progressFill=document.getElementById('scroll-progress-fill');
let scrollTicking=false;
const updateScrollProgress=()=>{
  const maxScroll=document.documentElement.scrollHeight-window.innerHeight;
  const percentage=maxScroll>0?Math.min(100,Math.max(0,(window.scrollY/maxScroll)*100)):0;
  if(progressFill)progressFill.style.height=`${percentage}%`;

  const marker=window.scrollY+(window.innerHeight*.45);
  let current=sections[0]?.id;
  sections.forEach(section=>{
    if(section.offsetTop<=marker)current=section.id;
  });
  if(current)setActiveSection(current);
  scrollTicking=false;
};

window.addEventListener('scroll',()=>{
  if(scrollTicking)return;
  scrollTicking=true;
  window.requestAnimationFrame(updateScrollProgress);
},{passive:true});
window.addEventListener('resize',updateScrollProgress);
updateScrollProgress();

    const style=document.createElement('link');
    style.rel='stylesheet';
    style.href='project-mundial.css?v=20260722-1801';
    document.head.appendChild(style);

    const projectScript=document.createElement('script');
    projectScript.src='project-mundial.js?v=20260722-1801';
    projectScript.defer=true;
    document.body.appendChild(projectScript);
  }

  if(document.readyState==='loading'){
    document.addEventListener('DOMContentLoaded',setupSite);
  }else{
    setupSite();
  }
})();
