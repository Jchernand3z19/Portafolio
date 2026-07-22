(() => {
  function setupSite(){
    const toggle=document.getElementById('menu-toggle');
    const links=document.getElementById('nav-links');
    if(toggle&&links){
      toggle.addEventListener('click',()=>{
        const open=links.classList.toggle('is-open');
        toggle.setAttribute('aria-expanded',String(open));
      });
      links.querySelectorAll('a').forEach(link=>link.addEventListener('click',()=>{
        links.classList.remove('is-open');
        toggle.setAttribute('aria-expanded','false');
      }));
    }

    const items=Array.from(document.querySelectorAll('.fade-in'));
    if('IntersectionObserver' in window){
      const appearanceObserver=new IntersectionObserver(entries=>{
        entries.forEach(entry=>{
          if(entry.isIntersecting){
            entry.target.classList.add('is-visible');
            appearanceObserver.unobserve(entry.target);
          }
        });
      },{threshold:.12});
      items.forEach(item=>appearanceObserver.observe(item));
    }else{
      items.forEach(item=>item.classList.add('is-visible'));
    }

    const sections=Array.from(document.querySelectorAll('[data-section]'));
    const navLinks=Array.from(document.querySelectorAll('.nav__link'));
    const progressDots=Array.from(document.querySelectorAll('.scroll-progress__dot'));

    function setActiveSection(id){
      navLinks.forEach(link=>link.classList.remove('is-active'));
      progressDots.forEach(dot=>dot.classList.remove('is-active'));

      const currentLink=navLinks.find(link=>link.getAttribute('href')==='#'+id);
      const currentDot=progressDots.find(dot=>dot.dataset.sectionDot===id);
      if(currentLink)currentLink.classList.add('is-active');
      if(currentDot)currentDot.classList.add('is-active');
    }

    if('IntersectionObserver' in window){
      const activeSectionObserver=new IntersectionObserver(entries=>{
        entries.forEach(entry=>{
          if(entry.isIntersecting)setActiveSection(entry.target.id);
        });
      },{rootMargin:'-45% 0px -45% 0px',threshold:0});
      sections.forEach(section=>activeSectionObserver.observe(section));
    }else if(sections.length){
      setActiveSection(sections[0].id);
    }

    const progressFill=document.getElementById('scroll-progress-fill');
    function updateProgressFill(){
      const maxScroll=document.documentElement.scrollHeight-window.innerHeight;
      const percentage=maxScroll>0?Math.min(100,Math.max(0,(window.scrollY/maxScroll)*100)):0;
      if(progressFill)progressFill.style.height=percentage+'%';
    }

    window.addEventListener('scroll',updateProgressFill,{passive:true});
    window.addEventListener('resize',updateProgressFill);
    updateProgressFill();

    const style=document.createElement('link');
    style.rel='stylesheet';
    style.href='project-mundial.css?v=20260722-1928';
    document.head.appendChild(style);

    const projectScript=document.createElement('script');
    projectScript.src='project-mundial.js?v=20260722-1928';
    projectScript.defer=true;
    document.body.appendChild(projectScript);
  }

  if(document.readyState==='loading'){
    document.addEventListener('DOMContentLoaded',setupSite);
  }else{
    setupSite();
  }
})();
