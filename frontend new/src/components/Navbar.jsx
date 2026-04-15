import React from "react";
import { Link } from "react-router-dom";
import { Button } from "./ui/button";
import { UserCircleIcon } from "@heroicons/react/24/outline";

const ParticipantNavbar = () => {
  return (
    <>
      <nav className="flex items-center justify-between bg-white shadow-md px-6 py-4">
        {/* HackHub Logo */}
        <Button
          asChild
          variant="link"
          className="text-2xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-blue-500 to-purple-600"
        >
          <Link to="/">CodeYatra</Link>
        </Button>

        {/* My Hackathons Section */}
        <Button asChild variant="ghost" className="text-lg font-medium hover:text-blue-600">
          <Link to="/myhack">My Hackathons</Link>
        </Button>

        {/* Profile Section */}
        <div className="flex items-center gap-2">
          <UserCircleIcon className="w-8 h-8 text-gray-600" />
          <Link
            to="/profile"
            className="text-gray-600 hover:text-blue-600 text-lg font-medium"
          >
            Profile
          </Link>
        </div>
      </nav>

      {/* Separator or Divider */}
      <div className="border-b-2 border-gray-200 shadow-sm" />
    </>
  );
};

export default ParticipantNavbar;
