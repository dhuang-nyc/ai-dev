export default function Logo() {
  return (
    <img
      src="/logo.png"
      alt="Capybara"
      className="w-12 h-12 rounded-full"
      onClick={() => (window.location.href = "/")}
    />
  );
}
